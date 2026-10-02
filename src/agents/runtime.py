"""Conversation-aware Core Router runtime for independent CrewAI routes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.agents.crew import CrewAIUnavailable, build_route_crew
from src.agents.guardrails import AgentGuardrailError, validate_agent_input, validate_agent_output
from src.agents.router import AgentRoute, route_turn
from src.agents.tools import competency_recommendation_tool, jev_resume_tool, policy_rag_tool, training_catalog_tool
from src.dify_client import DifyClient
from src.jev_client import JevClient
from src.sql_tools import SkillGraphDatabase


def run_agent_turn(message: str, *, conversation_state: dict[str, Any] | None = None, resume_text: str | None = None, has_resume: bool = False) -> dict[str, Any]:
    state = dict(conversation_state or {})
    try:
        validate_agent_input(message)
    except AgentGuardrailError as exc:
        return {"status": "blocked", "route": "guardrail", "answer": str(exc), "state_patch": {}}
    route = route_turn(message, has_resume=has_resume)
    if route == AgentRoute.SMALLTALK:
        return {"status": "local", "route": route.value, "answer": "Olá! Sou o SkillGraph. Posso ajudar com competências, trilhas, treinamentos e políticas de desenvolvimento.", "state_patch": {}}
    if route == AgentRoute.CLARIFY:
        return {"status": "clarify", "route": route.value, "answer": "Descreva um colaborador, uma competência, uma trilha, um treinamento ou uma política que deseja consultar.", "state_patch": {}}
    if os.getenv("CREWAI_ENABLED", "false").casefold() != "true":
        return {"status": "disabled", "route": route.value, "answer": "O fluxo multiagente está preparado, mas desativado neste ambiente.", "state_patch": {"last_route": route.value}}
    try:
        artifact_path = Path(os.getenv("SKILLGRAPH_ML_ARTIFACT", ".ml_artifacts/skillgraph_competency_tracks.pkl"))
        database = SkillGraphDatabase(Path(os.getenv("SKILLGRAPH_DATA_DIR", "data_bd")))
        jev = JevClient()
        dify = DifyClient.from_environment()
        def jev_tool(state_json: str) -> str:
            questions = JevClient.load_questions(str(Path(__file__).parents[2] / "config" / "jev_resume_questions.json"))
            return json.dumps(jev_resume_tool(jev, json.loads(state_json), questions), ensure_ascii=False)
        def prediction_tool(profile_json: str) -> str:
            profile = json.loads(profile_json)
            skills = {item.get("normalized_name") or item["name"]: float(item.get("level") or 0) for item in profile.get("skills", [])}
            return json.dumps(competency_recommendation_tool(artifact_path, skills), ensure_ascii=False)
        def training_tool(competency: str = "") -> str:
            return json.dumps(training_catalog_tool(database, competency or None), ensure_ascii=False, default=str)
        def policy_tool(question: str) -> str:
            return json.dumps(policy_rag_tool(dify, question), ensure_ascii=False, default=str)
        tools = {"JevResumeExtractionTool": jev_tool, "CompetencyRecommendationTool": prediction_tool, "TrainingCatalogTool": training_tool, "DifyPolicyTool": policy_tool}
        crew = build_route_crew(route.value, tools=tools)
        result = crew.kickoff(inputs={"message": message, "resume_text": resume_text or "", "conversation_state": json.dumps(state, ensure_ascii=False)})
        database.close()
        return {"status": "completed", "route": route.value, "answer": str(result), "state_patch": {"last_route": route.value}}
    except CrewAIUnavailable as exc:
        return {"status": "disabled", "route": route.value, "answer": str(exc), "state_patch": {"last_route": route.value}}
    except Exception as exc:
        return {"status": "error", "route": route.value, "answer": "O fluxo especialista não pôde ser concluído. Verifique a configuração local.", "error": str(exc), "state_patch": {"last_route": route.value}}


def run_agent_flow(message: str, *, resume_text: str | None = None) -> dict[str, Any]:
    return run_agent_turn(message, resume_text=resume_text)
