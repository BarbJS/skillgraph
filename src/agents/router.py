"""Conversation-level Core Router for independent specialist routes."""

from __future__ import annotations

import re
from enum import StrEnum


class AgentRoute(StrEnum):
    SMALLTALK = "smalltalk"
    RESUME = "resume_analysis"
    ML = "ml_prediction"
    GAP = "gap_analysis"
    TRAINING = "training_recommendation"
    POLICY = "policy_rag"
    STRUCTURED = "structured_data"
    CLARIFY = "clarify"


def route_turn(message: str, *, has_resume: bool = False) -> AgentRoute:
    normalized = " ".join(message.casefold().split())
    if re.fullmatch(
        r"(oi|olá|ola|bom dia|boa tarde|boa noite|tudo bem\??)[!. ]*", normalized
    ):
        return AgentRoute.SMALLTALK
    if has_resume or any(
        term in normalized
        for term in ("currículo", "curriculo", "resume", "vaga", "pdf")
    ):
        return AgentRoute.RESUME
    if any(
        term in normalized
        for term in (
            "trilha",
            "qual área",
            "qual area",
            "competências devo",
            "competencias devo",
            "perfil combina",
        )
    ):
        return AgentRoute.ML
    if any(
        term in normalized
        for term in ("lacuna", "gap", "prioridade de desenvolvimento")
    ):
        return AgentRoute.GAP
    if any(
        term in normalized
        for term in ("treinamento", "treinamentos", "curso", "cursos")
    ):
        return AgentRoute.TRAINING
    if any(
        term in normalized
        for term in ("política", "politica", "reembolso", "elegibilidade")
    ):
        return AgentRoute.POLICY
    if any(
        term in normalized
        for term in ("indicador", "quantos funcionários", "quantas pessoas")
    ):
        return AgentRoute.STRUCTURED
    return AgentRoute.CLARIFY
