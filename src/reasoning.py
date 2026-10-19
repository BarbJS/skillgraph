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
            step("Core Router", "Classificou a solicitação como pergunta documental.", tool="Core Router"),
            step("Policy Specialist", "Consultou o Chatflow Dify para recuperar evidências.", tool="DifyPolicyTool"),
            step("Dify/Weaviate", "Recuperou contexto documental para fundamentar a resposta.", tool="Dify/Weaviate"),
            step("Safety Reviewer", "Verificou escopo, evidência e ausência de dados sensíveis.", tool="Safety Reviewer"),
            step("Response Synthesizer", "Organizou a resposta final em linguagem natural.", tool="Response Synthesizer"),
        ]
    if route == "comparison":
        return [
            step("Core Router", "Selecionou a comparação documental.", tool="Core Router"),
            step("Policy Specialist", "Recuperou evidências documentais para os níveis solicitados.", tool="DifyPolicyTool"),
            step("Comparison", "Comparou os valores extraídos sem inventar dados.", tool="Dify/Weaviate"),
            step("Response Synthesizer", "Apresentou a comparação e suas fontes.", tool="Response Synthesizer"),
        ]
    if route == "sql_indicator":
        return [
            step("Core Router", "Classificou a solicitação como indicador estruturado.", tool="Core Router"),
            step("Structured Data Specialist", "Consultou funções permitidas no DuckDB.", tool="TrainingCatalogTool"),
            step("Safety Reviewer", "Verificou que o resultado é agregado e read-only.", tool="Safety Reviewer"),
            step("Response Synthesizer", "Organizou o indicador para apresentação.", tool="Response Synthesizer"),
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
