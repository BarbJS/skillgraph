"""Allowlisted tools used by the future CrewAI flow.

These functions are deliberately framework-agnostic so unit tests and the
application can use the same guarded boundaries before CrewAI is installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.dify_client import DifyClient
from src.jev_client import JevClient
from src.ml_pipeline import recommend_from_profile
from src.sql_tools import SkillGraphDatabase


class AgentToolError(RuntimeError):
    pass


def competency_recommendation_tool(
    artifact_path: Path, skills: dict[str, float]
) -> dict[str, Any]:
    return recommend_from_profile(artifact_path, skills)


def training_catalog_tool(
    database: SkillGraphDatabase, competency: str | None = None
) -> list[dict[str, Any]]:
    return database.training_catalog(competency=competency)


def policy_rag_tool(client: DifyClient, question: str) -> list[dict[str, Any]]:
    result = client.chat(question)
    return result.sources


def jev_resume_tool(
    client: JevClient, state: dict[str, Any], questions: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    result = client.analyze(state, questions)
    return {"model": result.model, "answers": result.answers, "usage": result.usage}
