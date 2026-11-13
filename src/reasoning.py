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
    stage: str,
    *,
    tool: str | None = None,
    status: str = "completed",
    summary: str = "A etapa estruturada foi concluída.",
) -> dict[str, Any]:
    """Create a public task summary without exposing model reasoning."""
    return step(stage, summary, status=status, tool=tool)


_AGENT_STEP_SPECS: dict[str, tuple[str, str | None]] = {
    "Core Router": (
        "Classificou a mensagem, confirmou a rota e coordenou os handoffs.",
        "Core Router",
    ),
    "Resume Interpreter": (
        "Interpretou o currículo sanitizado e preservou as evidências estruturadas.",
        "OCR/PyMuPDF + JEV (backend)",
    ),
    "Profile Normalizer": (
        "Normalizou aliases, níveis, evidências e removeu PII do perfil.",
        None,
    ),
    "Prediction Specialist": (
        "Executou a recomendação de trilhas e as explicações do modelo.",
        "CompetencyRecommendationTool",
    ),
    "Gap Analyst": (
        "Interpretou as prioridades e organizou as lacunas de desenvolvimento.",
        None,
    ),
    "Learning Path & Training Recommendation Agent": (
        "Consultou treinamentos existentes e verificou pré-requisitos.",
        "TrainingCatalogTool",
    ),
    "Competency & Development Specialist": (
        "Consultou o corpus de competências e desenvolvimento e preservou as fontes recuperadas.",
        "DifyRagTool",
    ),
    "Structured Data Specialist": (
        "Consultou o indicador autorizado em dados estruturados.",
        "CompetencyGapTool",
    ),
    "Competency Lookup Specialist": (
        "Consultou o caso específico autorizado em dados estruturados.",
        "CompetencyLookupTool",
    ),
    "Document Comparison Specialist": (
        "Recuperou evidências documentais para uma comparação source-backed.",
        "ComparisonTool",
    ),
    "Safety Reviewer": (
        "Validou schema, escopo, PII, evidência e necessidade de revisão humana.",
        "Safety Reviewer",
    ),
    "Response Synthesizer": (
        "Transformou os handoffs revisados em uma resposta contextualizada.",
        "Response Synthesizer",
    ),
}


def agent_execution_steps(
    route: str,
    *,
    completed_task_count: int | None = None,
    core_decision: Any = None,
) -> list[dict[str, Any]]:
    """Describe only the public agents completed by a CrewAI route."""
    from src.agents.crew import route_agent_roles

    roles = list(route_agent_roles(route))
    if completed_task_count is not None:
        roles = roles[: max(0, min(completed_task_count, len(roles)))]
    steps: list[dict[str, Any]] = []
    for role in roles:
        if role == "Core Router" and core_decision is not None:
            public_decision = core_decision_step(core_decision)
            if public_decision is not None:
                steps.append(public_decision)
                continue
        summary, tool = _AGENT_STEP_SPECS.get(
            role, ("Concluiu a etapa especializada da rota.", role)
        )
        steps.append(task_step(role, tool=tool, summary=summary))
    return sanitize_steps(steps)


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
    """Describe the public pipeline selected by the Core Router."""
    if route == "structured_data":
        roles = ("Core Router", "Structured Data Specialist", "Safety Reviewer", "Response Synthesizer")
    elif route == "training_recommendation":
        roles = ("Core Router", "Learning Path & Training Recommendation Agent", "Safety Reviewer", "Response Synthesizer")
    elif route == "competency_development_rag":
        roles = ("Core Router", "Competency & Development Specialist", "Safety Reviewer", "Response Synthesizer")
    elif route == "gap_analysis":
        roles = ("Core Router", "Gap Analyst", "Safety Reviewer", "Response Synthesizer")
    elif route == "competency_lookup":
        roles = ("Core Router", "Competency Lookup Specialist", "Safety Reviewer", "Response Synthesizer")
    elif route == "comparison":
        roles = ("Core Router", "Document Comparison Specialist", "Safety Reviewer", "Response Synthesizer")
    elif route == "ml_prediction":
        roles = ("Core Router", "Prediction Specialist", "Safety Reviewer", "Response Synthesizer")
    elif route == "resume_analysis":
        roles = ("Core Router", "Resume Interpreter", "Profile Normalizer", "Safety Reviewer", "Response Synthesizer")
    elif route == "blocked":
        return [step("Guardrail", "Interrompeu a solicitação antes de acessar ferramentas.", status="blocked", tool="Core Router")]
    elif route == "clarify":
        return [step("Core Router", "Solicitou esclarecimento antes de selecionar uma ferramenta.", status="skipped", tool="Core Router")]
    elif route == "smalltalk":
        return [step("Resposta local", "Reconheceu uma interação simples sem ferramenta externa.", tool="Core Router")]
    else:
        return [step("Core Router", "Encaminhou a solicitação para o fluxo apropriado.", tool="Core Router")]

    return [
        step(role, _AGENT_STEP_SPECS[role][0], tool=_AGENT_STEP_SPECS[role][1])
        for role in roles
    ]
