"""Optional TypeSafe/JEV adapter with an offline-safe disabled mode."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import requests


class JevError(RuntimeError):
    pass


@dataclass(frozen=True)
class JevResponse:
    model: str
    answers: dict[str, Any]
    usage: dict[str, Any]


class JevClient:
    def __init__(self, *, enabled: bool | None = None, api_key: str | None = None, base_url: str | None = None, model: str | None = None, timeout: float | None = None, session: requests.Session | None = None) -> None:
        self.enabled = (os.getenv("JEV_ENABLED", "false").casefold() == "true") if enabled is None else enabled
        self.api_key = api_key or os.getenv("TYPESAFE_API_KEY", "")
        self.base_url = (base_url or os.getenv("JEV_API_BASE_URL", "https://api.typesafe.ai/v1")).rstrip("/")
        self.model = model or os.getenv("JEV_MODEL", "jev-latest")
        self.timeout = timeout or float(os.getenv("JEV_TIMEOUT_SECONDS", "60"))
        self.max_retries = int(os.getenv("JEV_MAX_RETRIES", "1"))
        self.session = session or requests.Session()

    def analyze(self, state: dict[str, Any] | str, questions: dict[str, dict[str, Any]]) -> JevResponse:
        if not self.enabled:
            raise JevError("JEV está desativado; configure JEV_ENABLED=true após receber a chave.")
        if not self.api_key:
            raise JevError("TYPESAFE_API_KEY não configurada.")
        payload = {"state": state, "model": self.model, "questions": questions}
        try:
            response = self.session.post(
                f"{self.base_url}/systemone",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise JevError("A chamada ao JEV não foi concluída.") from exc
        if not isinstance(body, dict) or not isinstance(body.get("answers"), dict):
            raise JevError("O JEV retornou um formato inesperado.")
        return JevResponse(str(body.get("model", self.model)), body["answers"], body.get("usage", {}))

    @staticmethod
    def load_questions(path: str) -> dict[str, dict[str, Any]]:
        with open(path, encoding="utf-8") as stream:
            value = json.load(stream)
        if not isinstance(value, dict):
            raise JevError("O arquivo de perguntas JEV deve conter um objeto JSON.")
        return value
