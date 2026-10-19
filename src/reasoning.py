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
    "Policy Specialist": (
        "Consultou a política documental e preservou as fontes recuperadas.",
        "DifyPolicyTool",
    ),
    "Structured Data Specialist": (
        "Consultou o indicador autorizado em dados estruturados.",
        "CompetencyGapTool",
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
    """Describe the public sequential pipeline selected for a normal chat turn."""

    if route == "rag":
        return [
            step("Roteamento legado", "Classificou a solicitação como pergunta documental; nenhum agente CrewAI foi acionado.", tool="Roteador de intenções"),
            step("Dify/Weaviate", "Recuperou contexto documental e produziu a resposta pelo Chatflow.", tool="Dify/Weaviate"),
            step("Resposta final", "Apresentou a resposta e as fontes recuperadas.", tool="Streamlit"),
        ]
    if route == "comparison":
        return [
            step("Roteamento legado", "Selecionou a comparação documental; nenhum agente CrewAI foi acionado.", tool="Roteador de intenções"),
            step("Dify/Weaviate", "Recuperou as evidências documentais para os níveis solicitados.", tool="Dify/Weaviate"),
            step("Comparação", "Comparou os valores extraídos sem inventar dados.", tool="comparison"),
            step("Resposta final", "Apresentou a comparação e suas fontes.", tool="Streamlit"),
        ]
    if route == "sql_indicator":
        return [
            step("Roteamento legado", "Classificou a solicitação como indicador; nenhum agente CrewAI foi acionado.", tool="Roteador de intenções"),
            step("DuckDB", "Consultou funções read-only e retornou dados agregados.", tool="DuckDB read-only"),
            step("Resposta final", "Organizou o indicador para apresentação.", tool="Streamlit"),
        ]
    if route == "structured_data":
        return [
            step("Core Router", "Selecionou a consulta estruturada de lacunas.", tool="Core Router"),
            step("Structured Data Specialist", "Consultou as lacunas agregadas no DuckDB read-only.", tool="CompetencyGapTool"),
            step("Safety Reviewer", "Verificou que o resultado é agregado e não expõe identificadores.", tool="Safety Reviewer"),
            step("Response Synthesizer", "Organizou o indicador final para o usuário.", tool="Response Synthesizer"),
        ]
    if route == "training_recommendation":
        return [
            step("Core Router", "Selecionou a rota de recomendação de treinamentos.", tool="Core Router"),
            step("Learning Path & Training Recommendation Agent", "Consultou cursos e pré-requisitos permitidos.", tool="TrainingCatalogTool"),
            step("Safety Reviewer", "Validou cursos existentes, escopo e evidências.", tool="Safety Reviewer"),
            step("Response Synthesizer", "Redigiu a recomendação final.", tool="Response Synthesizer"),
        ]
    if route == "policy_rag":
        return [
            step("Core Router", "Selecionou a rota de política documental.", tool="Core Router"),
            step("Policy Specialist", "Consultou a política pelo Chatflow Dify.", tool="DifyPolicyTool"),
            step("Safety Reviewer", "Verificou fontes, escopo e ausência de decisão indevida.", tool="Safety Reviewer"),
            step("Response Synthesizer", "Redigiu a resposta baseada na política.", tool="Response Synthesizer"),
        ]
    labels = {
        "smalltalk": ("Resposta local", "Reconheceu uma interação simples sem ferramenta externa."),
        "competency_lookup": ("Consulta estruturada", "Consultou uma competência autorizada em modo read-only."),
        "blocked": ("Guardrail", "Interrompeu a solicitação antes de acessar ferramentas."),
    }
    label, summary = labels.get(route, ("Roteamento", "Encaminhou a solicitação para o fluxo apropriado."))
    tool = {"competency_lookup": "DuckDB read-only"}.get(route)
    return [
        step("Core Router", summary, tool="Core Router"),
        step(label, "Executou a etapa pública correspondente.", tool=tool),
    ]
