"""Google Gemini adapter for explicit DeepEval judge runs only."""

from __future__ import annotations

import json
import os
from typing import Any

import requests

try:
    from deepeval.models import DeepEvalBaseLLM
except ImportError:
    class DeepEvalBaseLLM:  # type: ignore[no-redef]
        pass


class LocalDeepEvalModel(DeepEvalBaseLLM):
    """Compatibility name for the evaluation-only Gemini judge adapter."""

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.model_name = model or os.getenv("EVAL_JUDGE_MODEL", "gemini-3.1-flash-lite")
        self.base_url = (base_url or os.getenv("EVAL_JUDGE_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")).rstrip("/")
        self.api_key = api_key or os.getenv("EVAL_JUDGE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
        self.session = session or requests.Session()
        self.provider = "google_gemini"
        self.usage_metadata: dict[str, Any] = {}
        self.last_usage: dict[str, Any] = {}
        if not self.api_key:
            raise RuntimeError("EVAL_JUDGE_API_KEY ou GEMINI_API_KEY não configurada.")
        super().__init__(model_name=self.model_name)

    def load_model(self, *args, **kwargs) -> "LocalDeepEvalModel":
        return self

    def generate(self, prompt: str, schema: Any | None = None) -> Any:
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 1200},
        }
        if schema is not None and hasattr(schema, "model_json_schema"):
            body["generationConfig"]["responseMimeType"] = "application/json"
            body["generationConfig"]["responseSchema"] = schema.model_json_schema()
        response = self.session.post(
            f"{self.base_url}/models/{self.model_name}:generateContent",
            params={"key": self.api_key},
            headers={"Content-Type": "application/json"},
            json=body,
            timeout=float(os.getenv("EVAL_JUDGE_TIMEOUT_SECONDS", "60")),
        )
        response.raise_for_status()
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
