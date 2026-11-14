"""Google Gemini embeddings adapter for explicit DeepEval runs."""

from __future__ import annotations

import os
from typing import Any

import requests

try:
    from deepeval.models import DeepEvalBaseEmbeddingModel
except ImportError:
    class DeepEvalBaseEmbeddingModel:  # type: ignore[no-redef]
        pass


class GeminiEvaluationEmbeddings(DeepEvalBaseEmbeddingModel):
    model_name = "gemini-embedding-001"
    provider = "google_gemini"

    def __init__(self, *, model: str | None = None, base_url: str | None = None, api_key: str | None = None, session: requests.Session | None = None) -> None:
        self.model_name = model or os.getenv("EVAL_EMBEDDING_MODEL", "gemini-embedding-001")
        self.base_url = (base_url or os.getenv("EVAL_EMBEDDING_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")).rstrip("/")
        self.api_key = api_key or os.getenv("EVAL_EMBEDDING_API_KEY") or os.getenv("GEMINI_API_KEY", "")
        self.session = session or requests.Session()
        if not self.api_key:
            raise RuntimeError("EVAL_EMBEDDING_API_KEY ou GEMINI_API_KEY não configurada.")
        try:
            super().__init__(model_name=self.model_name)
        except TypeError:
            pass

    def load_model(self):
        return self

    def embed_text(self, text: str) -> list[float]:
        response = self.session.post(
            f"{self.base_url}/models/{self.model_name}:embedContent",
            params={"key": self.api_key},
            headers={"Content-Type": "application/json"},
            json={"model": f"models/{self.model_name}", "content": {"parts": [{"text": text}]}},
            timeout=float(os.getenv("EVAL_EMBEDDING_TIMEOUT_SECONDS", "60")),
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        return [float(value) for value in payload["embedding"]["values"]]

    async def a_embed_text(self, text: str) -> list[float]:
        return self.embed_text(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]

    async def a_embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self.embed_texts(texts)

    def get_model_name(self) -> str:
        return self.model_name
