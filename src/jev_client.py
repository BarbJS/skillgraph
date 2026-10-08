"""Optional TypeSafe/JEV adapter with confidence telemetry."""

from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import Any
import requests
from src.privacy import sanitize, contains_protected_pii

try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass


def _request_verify() -> bool | str:
    """Use system truststore unless explicitly overridden for local debugging."""
    return os.getenv("JEV_VERIFY_TLS", "true").casefold() != "false"


def _request_error_message(exc: Exception) -> str:
    if isinstance(exc, requests.exceptions.SSLError):
        return "A chamada ao JEV falhou na validação TLS; instale/atualize a cadeia de certificados do ambiente."
    return "A chamada ao JEV não foi concluída."


class JevError(RuntimeError):
    pass


@dataclass(frozen=True)
class JevResponse:
    model: str
    answers: dict[str, Any]
    usage: dict[str, Any]
    confidence_by_question: dict[str, float]
    confidence_mean: float | None
    confidence_min: float | None


def _confidence(answers):
    values = {}
    for key, a in answers.items():
        if not isinstance(a, dict):
            continue
        value = (
            a.get("confidence")
            if a.get("confidence") is not None
            else (a.get("noul") if a.get("type") == "noul" else None)
        )
        if isinstance(value, (int, float)):
            values[str(key)] = max(0, min(1, float(value)))
    return values


class JevClient:
    def __init__(
        self,
        *,
        enabled=None,
        api_key=None,
        base_url=None,
        model=None,
        timeout=None,
        session=None,
        trace=None,
    ):
        self.enabled = (
            (os.getenv("JEV_ENABLED", "false").casefold() == "true")
            if enabled is None
            else enabled
        )
        self.api_key = api_key or os.getenv("TYPESAFE_API_KEY", "")
        self.base_url = (
            base_url or os.getenv("JEV_API_BASE_URL", "https://api.typesafe.ai/v1")
        ).rstrip("/")
        self.model = model or os.getenv("JEV_MODEL", "jev-latest")
        self.timeout = timeout or float(os.getenv("JEV_TIMEOUT_SECONDS", "60"))
        self.session = session or requests.Session()
        self.trace = trace

    def analyze(self, state, questions):
        if not self.enabled:
            raise JevError(
                "JEV está desativado; configure JEV_ENABLED=true após receber a chave."
            )
        if not self.api_key:
            raise JevError("TYPESAFE_API_KEY não configurada.")
        if contains_protected_pii(str(state)):
            raise JevError(
                "O state contém dados pessoais; remova-os antes de usar o JEV."
            )
        span = (
            self.trace.span("jev.systemone", "jev", task_name="systemone")
            if self.trace
            else None
        )
        if span:
            span.__enter__()
        try:
            r = self.session.post(
                f"{self.base_url}/systemone",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "state": sanitize(state),
                    "model": self.model,
                    "questions": questions,
                },
                timeout=self.timeout,
                verify=_request_verify(),
            )
            r.raise_for_status()
            body = r.json()
        except (requests.RequestException, ValueError) as exc:
            if span:
                span.__exit__(type(exc), exc, exc.__traceback__)
            raise JevError(_request_error_message(exc)) from exc
        if not isinstance(body, dict) or not isinstance(body.get("answers"), dict):
            if span:
                span.__exit__(ValueError, ValueError("invalid response"), None)
            raise JevError("O JEV retornou um formato inesperado.")
        values = _confidence(body["answers"])
        mean = sum(values.values()) / len(values) if values else None
        minimum = min(values.values()) if values else None
        usage = body.get("usage", {})
        if span:
            span.set_usage(
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
                cost=0.0,
            )
            span.record.metadata.update(
                {
                    "confidence_mean": mean,
                    "confidence_min": minimum,
                    "confidence_by_question": values,
                }
            )
            span.__exit__(None, None, None)
        return JevResponse(
            str(body.get("model", self.model)),
            body["answers"],
            usage,
            values,
            mean,
            minimum,
        )

    @staticmethod
    def load_questions(path):
        value = json.loads(open(path, encoding="utf-8").read())
        if not isinstance(value, dict):
            raise JevError("O arquivo de perguntas JEV deve conter um objeto JSON.")
        return value
