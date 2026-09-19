"""Route Etapa 1 questions to safe indicators, smalltalk, comparisons, or RAG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.comparison import extract_hours, levels_in_question
from src.dify_client import DifyClient, DifyClientError
from src.intent_router import Intent, extract_case_ids
from src.smalltalk import smalltalk_answer
from src.sql_tools import SkillGraphDatabase


@dataclass(frozen=True)
class RoutedAnswer:
    route: Intent
    answer: str
    rows: list[dict[str, Any]] | None = None
    reason: str = ""


def answer_smalltalk_question(question: str) -> RoutedAnswer:
    return RoutedAnswer(
        Intent.SMALLTALK,
        smalltalk_answer(question),
        reason="Mensagem social respondida sem consulta documental.",
    )


def _dify_client() -> DifyClient:
    return DifyClient.from_environment()


def answer_comparison_question(question: str) -> RoutedAnswer:
    """Retrieve evidence for each target, then compare extracted values."""

    levels = levels_in_question(question)
    if len(levels) < 2:
        return RoutedAnswer(
            Intent.COMPARISON,
            "Informe pelo menos dois níveis de cargo para comparar.",
        )
    try:
        client = _dify_client()
        sources: list[dict[str, Any]] = []
        for level in levels:
            retrieval_query = (
                f"{question}\n"
                f"Recupere a evidência documental da métrica perguntada para o nível {level}. "
                "Use a fonte normativa ou a tabela correspondente; não compare nem invente valores."
            )
            sources.extend(client.chat(retrieval_query).sources)
        extracted = extract_hours(sources, levels)
        return RoutedAnswer(
            Intent.COMPARISON,
            extracted.answer,
            extracted.rows,
            "; ".join(extracted.sources + (extracted.explanation,)),
        )
    except DifyClientError:
        return RoutedAnswer(
            Intent.COMPARISON,
            "Não foi possível recuperar evidências suficientes para a comparação.",
        )


def answer_structured_question(
    question: str, database: SkillGraphDatabase
) -> RoutedAnswer:
    """Answer aggregate questions with deterministic, read-only DuckDB functions."""

    normalized = question.lower()
    if any(word in normalized for word in ("treinamento", "treinamentos", "curso", "cursos")):
        rows = database.training_catalog()
        reason = "Catálogo consultado diretamente nas tabelas treinamentos e competencias."
        answer = "Este é o catálogo de treinamentos disponível nos dados estruturados."
    else:
        rows = database.competency_gaps()
        reason = "Lacunas calculadas diretamente nas tabelas funcionario_competencia e competencias."
        answer = "Este é o resumo das maiores lacunas encontrado nos dados estruturados."
    return RoutedAnswer(Intent.SQL_INDICATOR, answer, rows, reason)


def answer_competency_question(
    question: str, database: SkillGraphDatabase
) -> RoutedAnswer:
    """Answer an explicit employee/competency lookup without predictive logic."""

    employee, competency = extract_case_ids(question)
    if not employee or not competency:
        return RoutedAnswer(
            Intent.COMPETENCY_LOOKUP,
            "Para consultar uma competência específica, informe funcionário e competência, por exemplo: F0001 e COMP003.",
        )

    row = database.competency_case(employee, competency)
    if row is None:
        return RoutedAnswer(
            Intent.COMPETENCY_LOOKUP,
            f"Não encontrei um registro para {employee} e {competency} nos dados sintéticos disponíveis.",
        )

    gap = int(row["nivel_atual"]) < int(row["nivel_obrigatorio"])
    status = "abaixo do nível obrigatório" if gap else "no nível obrigatório ou acima"
    answer = (
        f"**Consulta de competência**\n\nCaso: {employee} / {row['competencia']}\n\n"
        f"Nível atual: {row['nivel_atual']}\n\n"
        f"Nível obrigatório: {row['nivel_obrigatorio']}\n\n"
        f"Situação observada: **{status}**.\n\n"
        "Esta consulta descreve os dados disponíveis e não constitui decisão de promoção ou punição."
    )
    reason = "Consulta direta em DuckDB: funcionario_competencia + competencias."
    return RoutedAnswer(Intent.COMPETENCY_LOOKUP, answer, reason=reason)
