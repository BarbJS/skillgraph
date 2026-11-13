"""Allowlisted tools used by the future CrewAI flow.

These functions are deliberately framework-agnostic so unit tests and the
application can use the same guarded boundaries before CrewAI is installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.comparison import extract_hours, levels_in_question
from src.dify_client import DifyClient
from src.jev_client import JevClient
from src.sql_tools import SkillGraphDatabase


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
    """Retrieve the answer and evidence from the complete corpus."""
    result = client.chat(question)
    return {
        "answer": result.answer,
        "sources": result.sources,
        "conversation_id": result.conversation_id,
        "message_id": result.message_id,
        "supported": bool(result.answer and result.sources),
    }


# Compatibility alias for callers that persisted the old tool name.
policy_rag_tool = rag_tool


def jev_resume_tool(
    client: JevClient, state: dict[str, Any], questions: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    result = client.analyze(state, questions)
    return {"model": result.model, "answers": result.answers, "usage": result.usage}
