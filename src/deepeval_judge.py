"""Google Gemini adapter for explicit DeepEval judge runs only."""

from __future__ import annotations

import json
import os
from typing import Any

import requests

_NATIVE_SCHEMA_KEYS = {
    "description",
    "enum",
    "format",
    "items",
    "maxItems",
    "maxLength",
    "maxProperties",
    "minItems",
    "minLength",
    "minProperties",
    "nullable",
    "pattern",
    "properties",
    "propertyOrdering",
    "required",
    "type",
}
_JSON_TO_GEMINI_TYPE = {
    "array": "ARRAY",
    "boolean": "BOOLEAN",
    "integer": "INTEGER",
    "number": "NUMBER",
    "object": "OBJECT",
    "string": "STRING",
}


def _gemini_schema(schema: Any) -> dict[str, Any]:
    """Convert a Pydantic/DeepEval schema to Gemini's Schema format.

    DeepEval passes Pydantic JSON Schema objects to ``generate``. Gemini's
    native REST API accepts a smaller dialect: types are uppercase and local
    ``$ref``/``$defs`` and nullable ``anyOf`` nodes must be expanded first.
    """
    raw_schema = schema.model_json_schema()
    definitions = raw_schema.get("$defs", {})
    return _convert_schema_node(raw_schema, definitions=definitions, seen_refs=set())


def _convert_schema_node(
    node: Any,
    *,
    definitions: dict[str, Any],
    seen_refs: set[str],
) -> dict[str, Any]:
    if not isinstance(node, dict):
        return {}

    reference = node.get("$ref")
    if isinstance(reference, str) and reference.startswith("#/$defs/"):
        name = reference.removeprefix("#/$defs/")
        if name not in seen_refs and name in definitions:
            return _convert_schema_node(
                definitions[name],
                definitions=definitions,
                seen_refs=seen_refs | {name},
            )

    alternatives = node.get("anyOf") or node.get("oneOf")
    if isinstance(alternatives, list) and alternatives:
        non_null = [item for item in alternatives if item.get("type") != "null"]
        if non_null:
            converted = _convert_schema_node(
                non_null[0], definitions=definitions, seen_refs=seen_refs
            )
            if len(non_null) < len(alternatives):
                converted["nullable"] = True
            return converted

    converted: dict[str, Any] = {}
    raw_type = node.get("type")
    if isinstance(raw_type, list):
        non_null_types = [item for item in raw_type if item != "null"]
        raw_type = non_null_types[0] if non_null_types else None
        if "null" in node["type"]:
            converted["nullable"] = True
    if isinstance(raw_type, str):
        converted["type"] = _JSON_TO_GEMINI_TYPE.get(raw_type, raw_type.upper())

    for key in ("description", "format", "pattern", "enum", "propertyOrdering"):
        value = node.get(key)
        if value is not None:
            converted[key] = value

    for key in (
        "maxItems",
        "maxLength",
        "maxProperties",
        "minItems",
        "minLength",
        "minProperties",
    ):
        value = node.get(key)
        if value is not None:
            converted[key] = value

    if isinstance(node.get("items"), dict):
        converted["items"] = _convert_schema_node(
            node["items"], definitions=definitions, seen_refs=seen_refs
        )

    if isinstance(node.get("properties"), dict):
        converted["properties"] = {
            str(name): _convert_schema_node(
                child, definitions=definitions, seen_refs=seen_refs
            )
            for name, child in node["properties"].items()
        }

    required = node.get("required")
    if isinstance(required, list):
        converted["required"] = [str(name) for name in required]

    return {
        key: value for key, value in converted.items() if key in _NATIVE_SCHEMA_KEYS
    }


def _http_error_detail(response: Any) -> str:
    try:
        payload = response.json()
    except (AttributeError, ValueError, json.JSONDecodeError):
        payload = getattr(response, "text", "")
    if isinstance(payload, dict):
        error = payload.get("error", payload)
        if isinstance(error, dict):
            payload = error.get("message", error)
    detail = str(payload).strip()
    return detail[:600] if detail else "sem detalhes retornados pela API"

_NATIVE_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

try:
    from deepeval.models import DeepEvalBaseLLM
except ImportError:
    class DeepEvalBaseLLM:  # type: ignore[no-redef]
        pass


class LocalDeepEvalModel(DeepEvalBaseLLM):
    """Gemini adapter that supports DeepEval structured schemas."""

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.model_name = self._native_model_name(
            model or os.getenv("EVAL_JUDGE_MODEL", "gemini-3.1-flash-lite")
        )
        self.base_url = _NATIVE_GEMINI_BASE_URL
        # Keep the configured endpoint for diagnostics only. Native judge calls
        # always use the canonical Google Gemini REST endpoint, so a stale
        # Streamlit secret cannot redirect evaluation to /openai.
        self.configured_base_url = self._native_base_url(
            base_url
            or os.getenv(
                "EVAL_JUDGE_BASE_URL",
                _NATIVE_GEMINI_BASE_URL,
            )
        )
        self.api_key = (
            api_key
            or os.getenv("EVAL_JUDGE_API_KEY")
            or os.getenv("GEMINI_API_KEY", "")
        )
        self.session = session or requests.Session()
        self.provider = "google_gemini"
        self.usage_metadata: dict[str, Any] = {}
        self.last_usage: dict[str, Any] = {}
        if not self.api_key:
            raise RuntimeError("EVAL_JUDGE_API_KEY ou GEMINI_API_KEY não configurada.")
        super().__init__(model_name=self.model_name)

    @staticmethod
    def _native_model_name(value: str) -> str:
        normalized = value.strip()
        if normalized.startswith("models/"):
            normalized = normalized[len("models/"):]
        if normalized.startswith("gemini/"):
            normalized = normalized[len("gemini/"):]
        if ":generateContent" in normalized:
            normalized = normalized.split(":generateContent", 1)[0]
        return normalized.strip("/")

    @staticmethod
    def _native_base_url(value: str) -> str:
        normalized = value.strip().rstrip("/")
        # The native Gemini REST API must use /v1beta. Any /openai suffix or
        # segment belongs to an OpenAI-compatible integration and is invalid
        # for the native generateContent endpoint.
        marker = "/openai"
        if marker in normalized:
            normalized = normalized.split(marker, 1)[0].rstrip("/")
        if normalized.endswith("/v1"):
            normalized = normalized[: -len("/v1")] + "/v1beta"
        if not normalized.endswith("/v1beta"):
            normalized = normalized + "/v1beta"
        return normalized

    def request_url(self) -> str:
        """Return the exact native Gemini URL prefix used by the judge."""
        return f"{self.base_url}/models/{self.model_name}:generateContent"

    def load_model(self, *args, **kwargs) -> "LocalDeepEvalModel":
        return self

    def diagnostics(self) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "base_url": self.base_url,
            "configured": bool(self.api_key),
        }

    def generate(self, prompt: str, schema: Any | None = None) -> Any:
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 1200},
        }
        if schema is not None and hasattr(schema, "model_json_schema"):
            body["generationConfig"]["responseMimeType"] = "application/json"
            body["generationConfig"]["responseSchema"] = _gemini_schema(schema)
        response = self.session.post(
            self.request_url(),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            json=body,
            timeout=float(os.getenv("EVAL_JUDGE_TIMEOUT_SECONDS", "60")),
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = _http_error_detail(response)
            raise RuntimeError(
                f"Gemini judge HTTP {getattr(response, 'status_code', 'error')}: {detail}"
            ) from exc
        except Exception:
            # Test doubles and alternate HTTP clients may expose an error
            # without using requests.HTTPError; keep the diagnostic sanitized.
            raise
        payload = response.json()
        self.last_usage = payload.get("usageMetadata", {}) if isinstance(payload, dict) else {}
        text = "".join(
            str(part.get("text", ""))
            for part in payload["candidates"][0]["content"]["parts"]
            if isinstance(part, dict)
        ).strip()
        if schema is not None and hasattr(schema, "model_validate"):
            return schema.model_validate(json.loads(text))
        return text

    async def a_generate(self, prompt: str, schema: Any | None = None) -> Any:
        return self.generate(prompt, schema)

    def get_model_name(self) -> str:
        return self.model_name

    def get_model(self) -> "LocalDeepEvalModel":
        return self
