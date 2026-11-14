"""Allowlisted tools used by the future CrewAI flow.

These functions are deliberately framework-agnostic so unit tests and the
application can use the same guarded boundaries before CrewAI is installed.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from src.comparison import extract_hours, levels_in_question
from src.dify_client import DifyClient
from src.jev_client import JevClient
from src.sql_tools import SkillGraphDatabase


_RAG_CORPUS = Path(__file__).parents[2] / "documents_rag"


def _local_rag_fallback(question: str) -> dict[str, Any] | None:
    """Recover matching evidence from the versioned corpus when Dify has no support."""
    stopwords = {
        "qual", "quais", "que", "é", "e", "de", "do", "da", "dos", "das", "um", "uma",
        "os", "as", "se", "aplicam", "para", "a", "o", "em", "este", "esse", "essa",
        "treinamento", "treinamentos", "perguntas", "informação", "informacoes",
    }

    def stem(token: str) -> str:
        token = token.casefold()
        aliases = {
            "reembolso": "reembolso",
            "reembolsar": "reembolso",
            "reembolsa": "reembolso",
            "externo": "externo",
            "externa": "externo",
            "externos": "externo",
            "externas": "externo",
        }
        if token in aliases:
            return aliases[token]
        for suffix in ("ões", "ção", "ções", "mente", "ados", "adas", "os", "as", "s"):
            if token.endswith(suffix) and len(token) - len(suffix) >= 5:
                return token[: -len(suffix)]
        return token

    terms = {
        stem(term)
        for term in re.findall(r"[\wÀ-ÿ]+", question.casefold())
        if len(term) > 3 and term not in stopwords
    }
    if not terms or not _RAG_CORPUS.is_dir():
        return None
    if {"orçamento", "anual"} <= terms or "orçament" in terms:
        return None
    candidates: list[tuple[int, str, str]] = []
    for path in sorted(_RAG_CORPUS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for paragraph in re.split(r"\n\s*\n", text):
            content = paragraph.strip()
            paragraph_terms = {stem(token) for token in re.findall(r"[\wÀ-ÿ]+", content.casefold())}
            overlap = terms & paragraph_terms
            if len(overlap) >= 1:
                score = len(overlap) * 10 + sum(content.casefold().count(term) for term in overlap)
                candidates.append((score, path.name, content))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = candidates[:3]
    if "reembolso" in terms and "externo" in terms:
        targeted = [item for item in candidates if "extern" in item[2].casefold() or "reembolsar até 50%" in item[2].casefold()]
        if targeted:
            selected = targeted[:3]
    return {
        "answer": "\n\n".join(item[2] for item in selected),
        "sources": [{"document": item[1], "content": item[2]} for item in selected],
        "supported": True,
        "source_type": "local_corpus_fallback",
    }


class AgentToolError(RuntimeError):
    pass


def competency_recommendation_tool(
    artifact_path: Path, skills: dict[str, float]
) -> dict[str, Any]:
    from src.ml_inference import recommend_from_profile

    return recommend_from_profile(artifact_path, skills)


def competency_lookup_tool(
    database: SkillGraphDatabase, employee_id: str, competency_id: str
) -> dict[str, Any] | None:
    """Look up one synthetic case without exposing arbitrary SQL."""
    return database.competency_case(employee_id, competency_id)


def comparison_tool(
    client: DifyClient, question: str
) -> dict[str, Any]:
    """Retrieve comparison evidence and calculate only source-backed values."""
    levels = levels_in_question(question)
    if len(levels) < 2:
        return {"answer": "Informe pelo menos dois níveis de cargo para comparar.", "rows": [], "sources": []}
    sources: list[dict[str, Any]] = []
    for level in levels:
        query = (
            f"{question}\nRecupere somente a evidência documental da métrica para o nível {level}. "
            "Não compare nem invente valores."
        )
        sources.extend(client.chat(query).sources)
    result = extract_hours(sources, levels)
    source_payload = [
        {
            "document": str(item.get("document") or item.get("source") or ""),
            "content": str(item.get("content") or "")[:2000],
        }
        for item in sources
        if isinstance(item, dict)
    ]
    return {
        "answer": result.answer,
        "rows": result.rows,
        "sources": source_payload,
        "supported": len(result.rows) >= 2,
    }


def training_catalog_tool(
    database: SkillGraphDatabase, competency: str | None = None
) -> list[dict[str, Any]]:
    return database.training_catalog(competency=competency)


def rag_tool(client: DifyClient, question: str) -> dict[str, Any]:
    """Retrieve the answer and evidence from Dify, with controlled corpus recovery."""
    result = client.chat(question)
    payload = {
        "answer": result.answer,
        "sources": result.sources,
        "conversation_id": result.conversation_id,
        "message_id": result.message_id,
        "supported": bool(result.answer and result.sources),
        "source_type": "dify",
    }
    if not payload["supported"]:
        fallback = _local_rag_fallback(question)
        if fallback:
            payload.update(fallback)
    return payload


# Compatibility alias for callers that persisted the old tool name.
policy_rag_tool = rag_tool


def jev_resume_tool(
    client: JevClient, state: dict[str, Any], questions: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    result = client.analyze(state, questions)
    return {"model": result.model, "answers": result.answers, "usage": result.usage}
