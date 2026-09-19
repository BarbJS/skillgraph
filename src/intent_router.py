"""Deterministic first-pass intent router for SkillGraph Etapa 1."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class Intent(StrEnum):
    RAG = "rag"
    SQL_INDICATOR = "sql_indicator"
    COMPETENCY_LOOKUP = "competency_lookup"
    SMALLTALK = "smalltalk"
    COMPARISON = "comparison"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class Route:
    intent: Intent
    reason: str


_BLOCKED = (
    r"\bcpf\b",
    r"\brg\b",
    r"e-?mail pessoal",
    r"sal[aá]rio individual",
    r"endereço",
    r"ignore (as|suas) regras",
    r"mostre (o|as) prompt",
    r"revele (suas|as) instruções",
    r"\b(select|insert|update|delete|drop|alter)\b(?:\s+\w+){0,4}",
)
_SQL = (
    r"qual (departamento|área|area) tem",
    r"quantos? funcion",
    r"maior (déficit|deficit|lacuna)",
    r"quais competências? (possuem|têm|tem|estão)",
    r"abaixo do nível",
    r"indicador",
    r"por departamento",
    r"quais treinamentos? (estão|estao|disponíveis|disponiveis)",
    r"quais cursos? (estão|estao|disponíveis|disponiveis)",
)
_COMPETENCY = (
    r"situação.*competência",
    r"nível.*obrigatório",
    r"competência.*funcionário",
    r"competencia.*funcionario",
)
_SMALLTALK = (
    r"^(oi|olá|ola|bom dia|boa tarde|boa noite)[!,. ]*$",
    r"^(obrigad[oa]|valeu)[!,. ]*$",
    r"^tudo bem[?!. ]*$",
    r"^como você está[?!. ]*$",
    r"^como voce esta[?!. ]*$",
    r"^(tchau|até mais|ate mais)[!,. ]*$",
)
_COMPARISON = (r"compar", r"diferença", r"versus", r"\bvs\b")


def _is_smalltalk(normalized: str) -> bool:
    return len(normalized.split()) <= 6 and any(
        re.search(pattern, normalized) for pattern in _SMALLTALK
    )


def _is_comparison(normalized: str) -> bool:
    has_comparison = any(re.search(pattern, normalized) for pattern in _COMPARISON)
    has_measure = any(term in normalized for term in ("carga", "horas", "nível", "nivel"))
    return has_comparison and has_measure


def route_question(question: str) -> Route:
    normalized = " ".join(question.lower().split())
    if any(re.search(pattern, normalized) for pattern in _BLOCKED):
        return Route(
            Intent.BLOCKED,
            "A pergunta solicita dado sensível ou tenta ignorar guardrails.",
        )
    if _is_smalltalk(normalized):
        return Route(
            Intent.SMALLTALK,
            "Mensagem social simples, sem necessidade de consultar o corpus.",
        )
    if _is_comparison(normalized):
        return Route(
            Intent.COMPARISON,
            "A pergunta solicita comparação analítica de regras documentadas.",
        )
    if any(re.search(pattern, normalized) for pattern in _COMPETENCY):
        return Route(
            Intent.COMPETENCY_LOOKUP,
            "A pergunta solicita consulta de competência documentada.",
        )
    if any(re.search(pattern, normalized) for pattern in _SQL):
        return Route(
            Intent.SQL_INDICATOR,
            "A pergunta solicita indicador agregado ou comparação estruturada.",
        )
    return Route(Intent.RAG, "A pergunta segue para o Chatflow documental por padrão.")


def extract_case_ids(question: str) -> tuple[str | None, str | None]:
    employee = re.search(r"\bF\d{4}\b", question, flags=re.IGNORECASE)
    competency = re.search(r"\bCOMP\d{3}\b", question, flags=re.IGNORECASE)
    return (
        employee.group(0).upper() if employee else None,
        competency.group(0).upper() if competency else None,
    )
