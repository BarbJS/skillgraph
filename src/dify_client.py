"""Small API client for the published SkillGraph Dify Chatflow."""
from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

import requests

from src.observability import TraceContext


_TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}
_QUOTA_ERROR_MARKERS = (
    "quota",
    "resource exhausted",
    "too many requests",
    "rate limit",
    "rate_limit",
    "high demand",
)
_TRANSIENT_ERROR_MARKERS = (
    "temporarily unavailable",
    "temporary unavailable",
    "try again later",
    "service unavailable",
    "overloaded",
    "overload",
    "timed out",
    "timeout",
    "tempo limite",
)


def _is_transient_detail(value: Any) -> bool:
    detail = str(value or "").casefold()
    return any(marker in detail for marker in _TRANSIENT_ERROR_MARKERS)


def _is_quota_error(value: Any) -> bool:
    detail = str(value or "").casefold()
    return "http 429" in detail or any(
        marker in detail for marker in _QUOTA_ERROR_MARKERS
    )


def _is_transient_error(value: Any) -> bool:
    detail = str(value or "").casefold()
    if _is_quota_error(detail):
        return False
    if _is_transient_detail(detail):
        return True
    return any(f"http {status}" in detail for status in _TRANSIENT_HTTP_STATUS)


class _RetryableDifyError(RuntimeError):
    """Internal signal for a safe retry before any answer was streamed."""


class DifyClientError(RuntimeError):
    """Raised when the Dify API cannot complete a request."""


@dataclass
class ChatResult:
    answer: str = ""
    conversation_id: str = ""
    message_id: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    cost: float = 0.0
    cost_source: str = "local_or_unpriced"



def _usage_from_event(event: Mapping[str, Any]) -> dict[str, Any]:
    candidates = [
        event.get("usage"),
        event.get("metadata"),
        event.get("data"),
        event.get("message_end"),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            nested = candidate.get("usage")
            if isinstance(nested, dict):
                return nested
            nested = candidate.get("llm_usage")
            if isinstance(nested, dict):
                return nested
            metadata = candidate.get("metadata")
            if isinstance(metadata, dict):
                nested = metadata.get("usage") or metadata.get("llm_usage")
                if isinstance(nested, dict):
                    return nested
            if any(
                key in candidate
                for key in (
                    "prompt_tokens",
                    "input_tokens",
                    "completion_tokens",
                    "output_tokens",
                    "total_tokens",
                    "prompt_token_count",
                    "completion_token_count",
                    "total_token_count",
                )
            ):
                return candidate
    return {}


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _usage_value(usage: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        value = _number(usage.get(key))
        if value is not None:
            return int(value)
    return 0


def _cost_value(usage: Mapping[str, Any]) -> float:
    for key in ("cost", "total_cost", "total_cost_usd", "total_price"):
        value = _number(usage.get(key))
        if value is not None:
            return value
    return 0.0


def _estimate_tokens(text: str) -> int:
    """Conservative local estimate used only when provider usage is absent."""
    return max(0, (len(text) + 3) // 4)


def _usage_from_response_headers(response: requests.Response) -> dict[str, Any]:
    usage: dict[str, Any] = {}
    headers = getattr(response, "headers", {}) or {}
    for key, target in (
        ("x-prompt-tokens", "prompt_tokens"),
        ("x-input-tokens", "input_tokens"),
        ("x-completion-tokens", "completion_tokens"),
        ("x-output-tokens", "output_tokens"),
        ("x-total-tokens", "total_tokens"),
    ):
        value = headers.get(key)
        if value and value.isdigit():
            usage[target] = int(value)
    return usage


def _set_span_usage(span: Any, usage: Mapping[str, Any], *, query: str = "", answer: str = "") -> None:
    if not span:
        return
    input_tokens = _usage_value(
        usage,
        "input_tokens",
        "prompt_tokens",
        "prompt_token_count",
    )
    output_tokens = _usage_value(
        usage,
        "output_tokens",
        "completion_tokens",
        "completion_token_count",
    )
    total_tokens = _usage_value(usage, "total_tokens", "total_token_count")
    usage_available = input_tokens > 0 or output_tokens > 0 or total_tokens > 0
    if not usage_available:
        input_tokens = _estimate_tokens(query)
        output_tokens = _estimate_tokens(answer)
        usage_source = "local_estimate"
    else:
        usage_source = "provider_reported"
    cost = _cost_value(usage)
    span.set_usage(input_tokens=input_tokens, output_tokens=output_tokens, cost=cost)
    span.metadata.update(
        {
            "usage_available": usage_available,
            "usage_source": usage_source,
            "cost_source": "provider_reported" if cost else "local_or_unpriced",
        }
    )


def _is_dify_cloud_base(value: str) -> bool:
    return value.casefold() in {
        "https://api.dify.ai/v1",
        "https://api.dify.ai",
    }


def _text_from_workflow_output(value: Any) -> str:
    """Extract a user-facing answer from a Chatflow workflow output."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        for key in ("answer", "text", "response", "content", "output", "result"):
            candidate = _text_from_workflow_output(value.get(key))
            if candidate:
                return candidate
    if isinstance(value, list):
        for item in value:
            candidate = _text_from_workflow_output(item)
            if candidate:
                return candidate
    return ""


def _workflow_failure_detail(event: Mapping[str, Any]) -> str:
    data = event.get("data")
    if isinstance(data, Mapping):
        detail = data.get("error") or data.get("message") or data.get("status")
        if detail:
            return str(detail)
    return str(event.get("error") or event.get("message") or "status=failed")


class DifyClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        user_id: str,
        *,
        timeout: tuple[float, float] | None = None,
        session: requests.Session | None = None,
        trace: TraceContext | None = None,
        max_retries: int | None = None,
        retry_backoff_seconds: float | None = None,
        total_timeout_seconds: float | None = None,
    ):
        normalized_base_url = base_url.rstrip("/")
        if normalized_base_url.endswith("/v1") and not _is_dify_cloud_base(normalized_base_url):
            normalized_base_url = normalized_base_url[:-3].rstrip("/")
        if normalized_base_url.endswith("/chat-messages"):
            normalized_base_url = normalized_base_url[: -len("/chat-messages")].rstrip("/")
        self.base_url = normalized_base_url
        self.api_key = api_key
        self.user_id = user_id
        connect_timeout = self._positive_float(
            os.getenv("DIFY_CONNECT_TIMEOUT_SECONDS", "10"),
            "DIFY_CONNECT_TIMEOUT_SECONDS",
        )
        read_timeout = self._positive_float(
            os.getenv("DIFY_READ_TIMEOUT_SECONDS", "60"),
            "DIFY_READ_TIMEOUT_SECONDS",
        )
        if timeout is not None:
            connect_timeout, read_timeout = timeout
        self.timeout = (
            self._positive_float(connect_timeout, "DIFY_CONNECT_TIMEOUT_SECONDS"),
            self._positive_float(read_timeout, "DIFY_READ_TIMEOUT_SECONDS"),
        )
        self.total_timeout_seconds = self._positive_float(
            total_timeout_seconds
            if total_timeout_seconds is not None
            else os.getenv("DIFY_TOTAL_TIMEOUT_SECONDS", "120"),
            "DIFY_TOTAL_TIMEOUT_SECONDS",
        )
        self.session = session or requests.Session()
        self.trace = trace
        self.max_retries = self._nonnegative_int(
            max_retries,
            os.getenv("DIFY_MAX_RETRIES", "0"),
            "DIFY_MAX_RETRIES",
        )
        self.retry_backoff_seconds = self._nonnegative_float(
            retry_backoff_seconds,
            os.getenv("DIFY_RETRY_BACKOFF_SECONDS", "1"),
            "DIFY_RETRY_BACKOFF_SECONDS",
        )

    @staticmethod
    def _positive_float(value: float | str, name: str) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise DifyClientError(f"{name} deve ser numérico e maior que zero.") from exc
        if parsed <= 0:
            raise DifyClientError(f"{name} deve ser maior que zero.")
        return parsed

    @staticmethod
    def _nonnegative_int(value: int | None, configured: str, name: str) -> int:
        if value is not None:
            parsed = value
        else:
            try:
                parsed = int(configured.strip())
            except (AttributeError, TypeError, ValueError) as exc:
                raise DifyClientError(f"{name} deve ser um inteiro não negativo.") from exc
        if parsed < 0:
            raise DifyClientError(f"{name} deve ser um inteiro não negativo.")
        return parsed

    @staticmethod
    def _nonnegative_float(value: float | None, configured: str, name: str) -> float:
        if value is not None:
            parsed = value
        else:
            try:
                parsed = float(configured.strip())
            except (AttributeError, TypeError, ValueError) as exc:
                raise DifyClientError(f"{name} deve ser numérico e não negativo.") from exc
        if parsed < 0:
            raise DifyClientError(f"{name} deve ser numérico e não negativo.")
        return parsed

    def _reset_attempt_state(self, conversation_id: str) -> None:
        self._last_usage = {}
        self._stream_answer = ""
        self._stream_conversation_id = conversation_id
        self._stream_message_id = ""
        self._stream_sources = []

    def _retry_or_raise(
        self,
        detail: str,
        *,
        attempt: int,
        has_answer: bool,
    ) -> None:
        if (
            not has_answer
            and _is_transient_error(detail)
            and attempt < self.max_retries
        ):
            raise _RetryableDifyError(detail)
        raise DifyClientError(detail)

    def _stream_attempt(
        self,
        endpoint: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        *,
        attempt: int,
    ) -> Iterator[dict[str, Any]]:
        response_timeout = self.timeout
        deadline = getattr(self, "_stream_deadline", None)
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise requests.exceptions.Timeout("Dify total timeout exceeded")
            response_timeout = (
                min(response_timeout[0], remaining),
                min(response_timeout[1], remaining),
            )
        response = self.session.post(
            endpoint,
            headers=headers,
            json=payload,
            stream=True,
            timeout=response_timeout,
        )
        with response:
            if response.status_code in (401, 403):
                raise DifyClientError(
                    "A API do Dify recusou a chave. Verifique DIFY_API_KEY e confirme que ela pertence ao Chatflow local publicado."
                )
            if response.status_code == 404:
                raise DifyClientError(
                    "Endpoint do Chatflow não encontrado. Confirme que o Chatflow está publicado e que DIFY_API_BASE_URL aponta para a instância correta do Dify."
                )
            if response.status_code >= 400:
                detail = f"O Dify retornou HTTP {response.status_code}: {_safe_error_detail(response)}"
                self._retry_or_raise(
                    detail,
                    attempt=attempt,
                    has_answer=bool(self._stream_answer),
                )
            header_usage = _usage_from_response_headers(response)
            for event in _parse_sse(response.iter_lines(decode_unicode=True)):
                event_type = event.get("event")
                if event_type:
                    self._stream_event_types.append(str(event_type))
                if event_type in {"message", "agent_message"}:
                    self._stream_answer += str(event.get("answer", ""))
                    self._stream_conversation_id = str(
                        event.get("conversation_id") or self._stream_conversation_id
                    )
                    self._stream_message_id = str(
                        event.get("message_id") or self._stream_message_id
                    )
                elif event_type == "message_end":
                    self._stream_conversation_id = str(
                        event.get("conversation_id") or self._stream_conversation_id
                    )
                    self._stream_message_id = str(
                        event.get("message_id") or self._stream_message_id
                    )
                    self._stream_sources.extend(_extract_sources(event.get("metadata")))
                    self._stream_sources.extend(_extract_sources(event.get("data")))
                elif event_type == "workflow_finished":
                    status = str(event.get("status") or "")
                    data = event.get("data")
                    if isinstance(data, Mapping):
                        status = str(data.get("status") or status)
                    if status in {"failed", "stopped"}:
                        detail = f"O Chatflow falhou durante a execução: {_workflow_failure_detail(event)}"
                        self._retry_or_raise(
                            detail,
                            attempt=attempt,
                            has_answer=bool(self._stream_answer),
                        )
                    workflow_answer = _text_from_workflow_output(event.get("outputs"))
                    if not workflow_answer and isinstance(data, Mapping):
                        workflow_answer = _text_from_workflow_output(data.get("outputs"))
                    if workflow_answer and not self._stream_answer:
                        self._stream_answer = workflow_answer
                        yield {
                            "event": "message",
                            "answer": workflow_answer,
                            "conversation_id": self._stream_conversation_id,
                            "message_id": self._stream_message_id,
                        }
                elif event_type == "error":
                    detail = f"O Chatflow falhou durante a execução: {_workflow_failure_detail(event)}"
                    self._retry_or_raise(
                        detail,
                        attempt=attempt,
                        has_answer=bool(self._stream_answer),
                    )
                usage = _usage_from_event(event)
                if usage:
                    self._last_usage = usage
                elif header_usage:
                    self._last_usage = header_usage
                yield event

    @staticmethod
    def _retry_delay(backoff_seconds: float, attempt: int) -> float:
        return backoff_seconds * (2**attempt)

    @classmethod
    def from_environment(
        cls, *, trace: TraceContext | None = None
    ) -> "DifyClient":
        base_url = os.getenv("DIFY_API_BASE_URL", "http://localhost").strip()
        base_url = base_url.rstrip("/")
        if base_url.endswith("/v1") and not _is_dify_cloud_base(base_url):
            base_url = base_url[:-3].rstrip("/")
        if base_url.endswith("/chat-messages"):
            base_url = base_url[: -len("/chat-messages")].rstrip("/")
        if not base_url:
            raise DifyClientError("DIFY_API_BASE_URL não pode ser vazio.")
        api_key = os.getenv("DIFY_API_KEY", "").strip()
        user_id = os.getenv("DIFY_USER_ID", "skillgraph-local-user").strip()
        if not api_key:
            raise DifyClientError("DIFY_API_KEY não configurada. Preencha o .env local com a chave do Chatflow publicado.")
        if not user_id:
            raise DifyClientError("DIFY_USER_ID não pode ser vazio.")
        return cls(base_url, api_key, user_id, trace=trace)

    def stream_chat(self, query: str, *, conversation_id: str = "", inputs: Mapping[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        query = query.strip()
        if not query:
            raise DifyClientError("A pergunta não pode ser vazia.")
        payload = {"inputs": dict(inputs or {}), "query": query, "response_mode": "streaming", "conversation_id": conversation_id, "user": self.user_id}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "Accept": "text/event-stream"}
        span = self.trace.span("dify.chat_stream", "dify", task_name="chat-messages") if self.trace else None
        self._last_usage = {}
        self._stream_answer = ""
        self._stream_conversation_id = conversation_id
        self._stream_message_id = ""
        self._stream_sources = []
        self._stream_workflow_failure = ""
        self._stream_event_types = []
        self._stream_deadline = time.monotonic() + self.total_timeout_seconds
        if span:
            span.__enter__()
        try:
            endpoint = (
                f"{self.base_url}/chat-messages"
                if self.base_url.endswith("/v1")
                else f"{self.base_url}/v1/chat-messages"
            )
            for attempt in range(self.max_retries + 1):
                self._reset_attempt_state(conversation_id)
                try:
                    yield from self._stream_attempt(
                        endpoint,
                        payload,
                        headers,
                        attempt=attempt,
                    )
                    break
                except _RetryableDifyError as exc:
                    if attempt >= self.max_retries:
                        raise DifyClientError(str(exc)) from exc
                    delay = self._retry_delay(self.retry_backoff_seconds, attempt)
                    if delay:
                        time.sleep(delay)
        except requests.exceptions.Timeout as exc:
            raise DifyClientError(
                "O Chatflow do Dify excedeu o tempo limite. Tente novamente em alguns instantes."
            ) from exc
        except requests.RequestException as exc:
            raise DifyClientError("Não foi possível conectar à API do Dify. Confirme a URL, a chave e a disponibilidade do Chatflow.") from exc
        except Exception as exc:
            if isinstance(exc, DifyClientError):
                raise
            raise DifyClientError("O streaming do Dify falhou durante o consumo da resposta.") from exc
        finally:
            if span:
                _set_span_usage(
                    span,
                    getattr(self, "_last_usage", {}),
                    query=query,
                    answer=getattr(self, "_stream_answer", ""),
                )
                span.__exit__(None, None, None)
            self._last_usage = {}
            self._stream_answer = ""
            self._stream_conversation_id = conversation_id
            self._stream_message_id = ""
            self._stream_sources = []
            self._stream_deadline = None

    def chat(self, query: str, *, conversation_id: str = "", inputs: Mapping[str, Any] | None = None) -> ChatResult:
        result = ChatResult(conversation_id=conversation_id)
        for event in self.stream_chat(query, conversation_id=conversation_id, inputs=inputs):
            event_type = event.get("event")
            if event_type in {"message", "agent_message"}:
                result.answer += str(event.get("answer", ""))
                result.conversation_id = str(event.get("conversation_id") or result.conversation_id)
                result.message_id = str(event.get("message_id") or result.message_id)
            elif event_type == "message_end":
                result.conversation_id = str(event.get("conversation_id") or result.conversation_id)
                result.message_id = str(event.get("message_id") or result.message_id)
                result.sources.extend(_extract_sources(event.get("metadata")))
                result.sources.extend(_extract_sources(event.get("data")))
            elif event_type == "workflow_finished":
                data = event.get("data")
                status = str(event.get("status") or (data.get("status") if isinstance(data, Mapping) else ""))
                if status in {"failed", "stopped"}:
                    raise DifyClientError(
                        f"O Chatflow falhou durante a execução: {_workflow_failure_detail(event)}"
                    )
                if not result.answer:
                    result.answer = _text_from_workflow_output(event.get("outputs"))
                    if not result.answer and isinstance(data, Mapping):
                        result.answer = _text_from_workflow_output(data.get("outputs"))
            usage = _usage_from_event(event)
            if usage:
                result.usage = dict(usage)
                result.cost = _cost_value(usage)
                result.cost_source = (
                    "provider_reported" if result.cost else "local_or_unpriced"
                )
            elif event_type == "message_end":
                result.conversation_id = str(event.get("conversation_id") or result.conversation_id)

            if event_type == "error":
                raise DifyClientError(str(event.get("message") or event.get("code") or "O Dify retornou um erro durante o streaming."))
        if not result.answer:
            failure = getattr(self, "_stream_workflow_failure", "")
            failure = getattr(self, "_stream_workflow_failure", "")
            events = ", ".join(getattr(self, "_stream_event_types", []))
            detail = f" Detalhe: {failure}" if failure else ""
            event_detail = f" Eventos recebidos: {events}." if events else " Nenhum evento SSE foi recebido."
            raise DifyClientError(
                f"O Dify encerrou o streaming sem retornar uma resposta.{detail}{event_detail}"
            )
        return result


def _parse_sse(lines: Iterator[str | None]) -> Iterator[dict[str, Any]]:
    event_name = "message"
    data_lines: list[str] = []
    for raw_line in lines:
        line = (raw_line or "").strip()
        if not line:
            if data_lines:
                yield _event_payload(event_name, "\n".join(data_lines))
            event_name, data_lines = "message", []
        elif line.startswith("event:"):
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
    return {"event": event_name, **payload} if isinstance(payload, dict) else {"event": event_name, "data": payload}


def _extract_sources(metadata: Any) -> list[dict[str, Any]]:
    if isinstance(metadata, dict) and isinstance(metadata.get("metadata"), dict):
        metadata = metadata["metadata"]
    if not isinstance(metadata, dict):
        return []
    candidates = metadata.get("retriever_resources") or metadata.get("sources") or []
    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in candidates if isinstance(candidates, list) else []:
        if not isinstance(item, dict):
            continue
        document = str(item.get("document_name") or item.get("title") or item.get("name") or "").strip()
        content = str(item.get("content") or "").strip()
        if (document, content) not in seen:
            seen.add((document, content))
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
