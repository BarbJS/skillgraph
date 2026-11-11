"""Mandatory final-response boundary for user-visible answers."""

from __future__ import annotations

import json
from contextlib import nullcontext
from typing import Any, Mapping

from src.gemini_synthesizer import GeminiSynthesizer
from src.privacy import redact_text


def _safe_text(value: Any, *, limit: int = 12000) -> str:
    redacted, _ = redact_text(str(value or ""))
    return redacted[:limit]


def _safe_payload(value: Any) -> Any:
    """Sanitize response context before it crosses the Gemini boundary."""

    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, Mapping):
        return {
            str(key): _safe_payload(item)
            for key, item in value.items()
            if str(key).casefold()
            not in {"resume", "resume_text", "prompt", "chain_of_thought", "reasoning"}
        }
    if isinstance(value, list):
        return [_safe_payload(item) for item in value[:100]]
    return value


def synthesize_response(
    route: str,
    draft_answer: str,
    *,
    structured_context: Mapping[str, Any] | None = None,
    sources: list[Mapping[str, Any]] | None = None,
    table_rows: list[Mapping[str, Any]] | None = None,
    trace: Any = None,
) -> tuple[str, dict[str, Any]]:
    """Send every eligible user-visible answer through mandatory Gemini.

    There is intentionally no local fallback here. If the provider is not
    configured or fails, the caller receives the exception and must render an
    error instead of presenting an unsynthesized answer as final.
    """

    client = GeminiSynthesizer(enabled=True)
    payload = _safe_payload(
        {
            "route": route,
            "draft_answer": draft_answer,
            "structured_context": dict(structured_context or {}),
            "sources": list(sources or []),
            "table_rows": list(table_rows or []),
        }
    )
    # Keep a hard upper bound on the request body while preserving the draft.
    serialized = json.dumps(payload, ensure_ascii=False, default=str)
    if len(serialized) > 30000:
        payload["structured_context"] = _safe_text(
            json.dumps(payload.get("structured_context", {}), ensure_ascii=False),
            limit=8000,
        )
        payload["sources"] = []
        payload["table_rows"] = list(table_rows or [])[:20]

    span_context = (
        trace.span(
            "gemini.final_synthesis",
            "gemini",
            task_name="final_synthesis",
            metadata={
                "observation_type": "generation",
                "model": client.model,
                "route": route,
            },
        )
        if trace
        else nullcontext()
    )
    with span_context as span:
        result = client.synthesize(payload)
        if trace:
            span.set_usage(
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost=result.cost,
            )
            span.metadata.update(
                {
                    "usage_source": result.usage_source,
                    "cost_source": result.cost_source,
                }
            )
    return result.text, {
        "provider": "gemini",
        "model": result.model,
        "usage_source": result.usage_source,
        "cost_source": result.cost_source,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "total_tokens": result.total_tokens,
        "cost": result.cost,
    }
