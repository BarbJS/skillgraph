"""Public, sanitized execution summaries for the user interface.

These steps describe what the system did, not the private chain of thought of
any model or agent.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from src.agents.schemas import CoreRouteDecision

_PRIVATE_KEYS = {
    "thought",
    "thinking",
    "chain_of_thought",
    "reasoning",
    "prompt",
    "raw",
}


def _short_text(value: Any, limit: int = 500) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def core_decision_step(value: Any) -> dict[str, Any] | None:
    """Convert only the Core's public contract into a UI-safe step."""
    if isinstance(value, CoreRouteDecision):
        decision = value
    else:
        candidate = value
        if isinstance(value, str):
            try:
                candidate = json.loads(value)
            except json.JSONDecodeError:
                return None
        if not isinstance(candidate, dict) or _PRIVATE_KEYS.intersection(candidate):
            return None
        try:
            decision = CoreRouteDecision.model_validate(candidate)
        except Exception:
            return None
    return step(
        "Core Router",
        f"Intenção: {decision.intent}. Próximo agente: {decision.next_agent}. "
        f"Motivo: {_short_text(decision.reason)} Validação: {_short_text(decision.validation)}",
        tool="Core Router",
    )


def task_step(
    stage: str, *, tool: str | None = None, status: str = "completed"
) -> dict[str, Any]:
    """Create a generic public task summary without model output."""
    return step(stage, "A etapa estruturada foi concluída.", status=status, tool=tool)


def sanitize_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only the public reasoning schema and remove private fields."""
    result: list[dict[str, Any]] = []
    for item in steps:
        if not isinstance(item, dict) or _PRIVATE_KEYS.intersection(item):
            continue
        try:
            result.append(PublicReasoningStep.model_validate(item).model_dump())
        except Exception:
            continue
    return result


class PublicReasoningStep(BaseModel):
    """A safe, user-facing summary of one completed pipeline stage."""

    model_config = ConfigDict(extra="forbid")
    stage: str
    status: Literal["completed", "skipped", "blocked", "failed"]
    summary: str
    tool: str | None = None


def step(
    stage: str,
    summary: str,
    *,
    status: Literal["completed", "skipped", "blocked", "failed"] = "completed",
    tool: str | None = None,
) -> dict[str, Any]:
    """Build a sanitized execution step; never accepts model reasoning text."""

    return PublicReasoningStep(
        stage=stage,
        status=status,
        summary=summary,
        tool=tool,
    ).model_dump()


def route_steps(route: str) -> list[dict[str, Any]]:
    """Describe the deterministic route selected for a normal chat turn."""

    labels = {
        "smalltalk": (
            "Resposta local",
            "A mensagem foi reconhecida como uma interação simples.",
        ),
        "comparison": (
            "Comparação documental",
            "A solicitação foi encaminhada para comparação de evidências documentais.",
        ),
        "competency_lookup": (
            "Consulta estruturada",
            "A solicitação foi encaminhada para uma consulta read-only de competência.",
        ),
        "sql_indicator": (
            "Indicador estruturado",
            "A solicitação foi encaminhada para um indicador permitido.",
        ),
        "rag": (
            "RAG documental",
            "A solicitação foi encaminhada ao Chatflow documental.",
        ),
        "blocked": (
            "Guardrail",
            "A solicitação foi interrompida antes de acessar ferramentas.",
        ),
    }
    label, summary = labels.get(
        route, ("Roteamento", "A solicitação foi encaminhada para o fluxo apropriado.")
    )
    tool = {
        "competency_lookup": "DuckDB read-only",
        "sql_indicator": "DuckDB read-only",
        "rag": "Dify/Weaviate",
        "comparison": "Dify/Weaviate",
    }.get(route)
    return [
        step("Roteamento", summary, tool=tool),
        step(label, "O fluxo especializado foi executado.", tool=tool),
    ]
