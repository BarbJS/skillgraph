"""Deterministic Core Router for every SkillGraph conversation turn."""

from __future__ import annotations

import re
from enum import StrEnum


class AgentRoute(StrEnum):
    """Single source of truth for application conversation routes."""

    SMALLTALK = "smalltalk"
    RESUME = "resume_analysis"
    ML = "ml_prediction"
    GAP = "gap_analysis"
    TRAINING = "training_recommendation"
    RAG = "competency_development_rag"
    STRUCTURED = "structured_data"
    COMPETENCY_LOOKUP = "competency_lookup"
    COMPARISON = "comparison"
    CLARIFY = "clarify"
    BLOCKED = "blocked"


_SMALLTALK = re.compile(
    r"^(oi|olá|ola|bom dia|boa tarde|boa noite|tudo bem|obrigad[oa]|valeu|"
    r"tchau|até mais|ate mais)([!,.? ]*)$|^oi[,! ]+tudo bem[?!. ]*$",
    re.IGNORECASE,
)
_BLOCKED = (
    re.compile(r"\b(cpf|rg|cnpj)\b", re.IGNORECASE),
    re.compile(r"ignore (as|suas|todas as) regras|ignore o escopo|revele (o|seu|suas) prompt|mostre (as|suas) instruções", re.IGNORECASE),
    re.compile(r"\b(select|insert|update|delete|drop|alter)\b(?:\s+\w+){0,4}", re.IGNORECASE),
    re.compile(r"(api[_ -]?key|secret|password|token)\s*[:=]", re.IGNORECASE),
    re.compile(r"inclua este segredo|não o redija|nao o redija|\bsk-[A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
    re.compile(r"modelo sem restrições|desative os filtros|responda insultando", re.IGNORECASE),
)
_RESUME = ("currículo", "curriculo", "resume", "pdf")
_ML = (
    "qual trilha priorizar",
    "qual trilha combina",
    "qual trilha seguir",
    "qual trilha escolher",
    "trilha priorizada",
    "perfil combina",
    "competências devo desenvolver",
    "competencias devo desenvolver",
    "quais competências o colaborador precisa desenvolver",
    "quais competencias o colaborador precisa desenvolver",
    "próximo passo",
    "proximo passo",
)
_POLICY = (
    "política", "politica", "reembolso", "elegibilidade", "carga horária",
    "carga horaria", "horas de treinamento", "prazo para", "contam para",
    "conta para", "vale horas", "valem horas", "vale como carga",
    "valem como carga", "conta como carga", "contam como carga",
    "horário de trabalho", "horario de trabalho",
)
_TRAINING = ("treinamento", "treinamentos", "curso", "cursos")
_GAP = ("lacuna", "lacunas", "gap", "prioridade de desenvolvimento")
_INDICATOR = ("indicador", "quantos funcionários", "quantas pessoas", "agregado")
_COMPARISON = ("compar", "diferença", "diferenca", "versus", " vs ")


def _contains_any(normalized: str, terms: tuple[str, ...]) -> bool:
    return any(term in normalized for term in terms)


def _is_comparison(normalized: str) -> bool:
    return _contains_any(normalized, _COMPARISON) and _contains_any(
        normalized, ("carga", "horas", "nível", "nivel")
    )


def _is_ml_request(normalized: str) -> bool:
    if _contains_any(normalized, _ML):
        return True
    return (
        "trilha" in normalized
        and _contains_any(normalized, ("colaborador", "competência", "competencia", "python", "sql", "cloud", "machine learning"))
        and not normalized.startswith(("quais trilhas", "que trilhas", "lista de trilhas"))
    )


def _is_competency_lookup(normalized: str) -> bool:
    return bool(re.search(r"\bF\d{4}\b", normalized, re.IGNORECASE)) and bool(
        re.search(r"\bCOMP\d{3}\b", normalized, re.IGNORECASE)
    )


def _needs_clarification(normalized: str) -> bool:
    """Recognize underspecified questions before the broad documentary fallback."""
    if not normalized:
        return True
    if normalized in {"qual é o prazo?", "qual e o prazo?", "qual prazo?", "como funciona?", "me ajude?"}:
        return True
    return normalized.endswith("?") and len(normalized.split()) <= 4


def route_turn(
    message: str,
    *,
    has_resume: bool = False,
    conversation_state: dict[str, object] | None = None,
) -> AgentRoute:
    """Select exactly one route; no legacy router may be consulted afterward."""

    normalized = " ".join(str(message or "").casefold().split())
    if _SMALLTALK.fullmatch(normalized):
        return AgentRoute.SMALLTALK
    if any(pattern.search(normalized) for pattern in _BLOCKED):
        return AgentRoute.BLOCKED
    if has_resume or _contains_any(normalized, _RESUME):
        return AgentRoute.RESUME
    if _is_competency_lookup(normalized):
        return AgentRoute.COMPETENCY_LOOKUP
    if _is_comparison(normalized):
        return AgentRoute.COMPARISON
    if _is_ml_request(normalized):
        return AgentRoute.ML
    if _contains_any(normalized, _POLICY):
        return AgentRoute.RAG
    if _contains_any(normalized, _GAP) and _contains_any(
        normalized, ("treinamento", "treinamentos", "curso", "cursos")
    ):
        return AgentRoute.TRAINING
    if _contains_any(normalized, _INDICATOR) and not _contains_any(normalized, _TRAINING):
        return AgentRoute.STRUCTURED
    if _contains_any(normalized, _TRAINING):
        return AgentRoute.TRAINING
    if _contains_any(normalized, _GAP):
        state = conversation_state or {}
        if state.get("prediction") or state.get("employee_profile"):
            return AgentRoute.GAP
        return AgentRoute.STRUCTURED
    if _contains_any(normalized, _INDICATOR):
        return AgentRoute.STRUCTURED
    if _needs_clarification(normalized):
        return AgentRoute.CLARIFY
    return AgentRoute.RAG
