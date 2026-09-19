"""Small API client for the published SkillGraph Dify Chatflow."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

import requests


class DifyClientError(RuntimeError):
    """Raised when the Dify API cannot complete a request."""


@dataclass
class ChatResult:
    """Normalized answer and metadata returned by a Dify chat request."""

    answer: str = ""
    conversation_id: str = ""
    message_id: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)


class DifyClient:
    """Call a published Dify Chatflow without exposing its API key."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        user_id: str,
        *,
        timeout: tuple[float, float] = (10.0, 180.0),
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.user_id = user_id
        self.timeout = timeout
        self.session = session or requests.Session()

    @classmethod
    def from_environment(cls) -> "DifyClient":
        """Build the production Chatflow client from the local .env."""

        base_url = os.getenv("DIFY_API_BASE_URL", "http://localhost").strip()
        api_key = os.getenv("DIFY_API_KEY", "").strip()
        user_id = os.getenv("DIFY_USER_ID", "skillgraph-local-user").strip()
        if not api_key:
            raise DifyClientError(
                "DIFY_API_KEY não configurada. Preencha o .env local "
                "com a chave do Chatflow publicado."
            )
        if not user_id:
            raise DifyClientError("DIFY_USER_ID não pode ser vazio.")
        return cls(base_url, api_key, user_id)

    def stream_chat(
        self,
        query: str,
        *,
        conversation_id: str = "",
        inputs: Mapping[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield parsed SSE events from the Dify streaming endpoint."""

        query = query.strip()
        if not query:
            raise DifyClientError("A pergunta não pode ser vazia.")

        payload = {
            "inputs": dict(inputs or {}),
            "query": query,
            "response_mode": "streaming",
            "conversation_id": conversation_id,
            "user": self.user_id,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        try:
            response = self.session.post(
                f"{self.base_url}/v1/chat-messages",
                headers=headers,
                json=payload,
                stream=True,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise DifyClientError(
                "Não foi possível conectar ao Dify local. "
                "Confirme se os containers estão ativos."
            ) from exc

        with response:
            if response.status_code in (401, 403):
                raise DifyClientError(
                    "A API do Dify recusou a chave. Verifique DIFY_API_KEY "
                    "e confirme que ela pertence ao Chatflow local publicado."
                )
            if response.status_code == 404:
                raise DifyClientError(
                    "Endpoint do Chatflow não encontrado. Confirme que o app foi "
                    "publicado e que DIFY_API_BASE_URL aponta para http://localhost."
                )
            if response.status_code >= 400:
                detail = _safe_error_detail(response)
                raise DifyClientError(
                    f"O Dify retornou HTTP {response.status_code}: {detail}"
                )

            yield from _parse_sse(response.iter_lines(decode_unicode=True))

    def chat(
        self,
        query: str,
        *,
        conversation_id: str = "",
        inputs: Mapping[str, Any] | None = None,
    ) -> ChatResult:
        """Consume a complete streaming request into a normalized result."""

        result = ChatResult(conversation_id=conversation_id)
        for event in self.stream_chat(
            query,
            conversation_id=conversation_id,
            inputs=inputs,
        ):
            event_type = event.get("event")
            if event_type == "message":
                result.answer += str(event.get("answer", ""))
                result.conversation_id = str(
                    event.get("conversation_id") or result.conversation_id
                )
                result.message_id = str(event.get("message_id") or result.message_id)
            elif event_type == "message_end":
                result.conversation_id = str(
                    event.get("conversation_id") or result.conversation_id
                )
                result.message_id = str(event.get("message_id") or result.message_id)
                result.sources.extend(_extract_sources(event.get("metadata")))
                result.sources.extend(_extract_sources(event.get("data")))
            elif event_type == "error":
                raise DifyClientError(
                    str(
                        event.get("message")
                        or event.get("code")
                        or "O Dify retornou um erro durante o streaming."
                    )
                )
            elif event_type == "workflow_failed":
                data = event.get("data")
                message = data.get("error") if isinstance(data, dict) else None
                raise DifyClientError(
                    str(message or "O workflow do Dify falhou durante o streaming.")
                )
        if not result.answer:
            raise DifyClientError("O Dify encerrou o streaming sem retornar uma resposta.")
        return result


def _parse_sse(lines: Iterator[str | None]) -> Iterator[dict[str, Any]]:
    """Parse Dify's ``event:``/``data:`` server-sent event format."""

    event_name = "message"
    data_lines: list[str] = []
    for raw_line in lines:
        line = (raw_line or "").strip()
        if not line:
            if data_lines:
                yield _event_payload(event_name, "\n".join(data_lines))
            event_name = "message"
            data_lines = []
            continue
        if line.startswith("event:"):
            event_name = line.partition(":")[2].strip()
        elif line.startswith("data:"):
            data_lines.append(line.partition(":")[2].lstrip())

    if data_lines:
        yield _event_payload(event_name, "\n".join(data_lines))


def _event_payload(event_name: str, raw_data: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_data)
    except json.JSONDecodeError:
        payload = {"raw": raw_data}
    if isinstance(payload, dict):
        return {"event": event_name, **payload}
    return {"event": event_name, "data": payload}


def _extract_sources(metadata: Any) -> list[dict[str, Any]]:
    if isinstance(metadata, dict) and isinstance(metadata.get("metadata"), dict):
        metadata = metadata["metadata"]
    if not isinstance(metadata, dict):
        return []
    candidates = metadata.get("retriever_resources") or metadata.get("sources") or []
    if not isinstance(candidates, list):
        return []
    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in candidates:
        if not isinstance(item, dict):
            continue
        document = str(
            item.get("document_name")
            or item.get("title")
            or item.get("name")
            or ""
        ).strip()
        content = str(item.get("content") or "").strip()
        key = (document, content)
        if key in seen:
            continue
        seen.add(key)
        sources.append({"document": document, "content": content})
    return sources


def _safe_error_detail(response: requests.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict):
            return str(body.get("message") or body.get("code") or "erro sem detalhes")
    except (ValueError, requests.RequestException):
        pass
    return "erro sem detalhes"
