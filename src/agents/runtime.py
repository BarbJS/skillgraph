"""Conversation-aware Core Router runtime for independent CrewAI routes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.agents.crew import CrewAIUnavailable, build_route_crew
from src.agents.guardrails import AgentGuardrailError, validate_agent_input
from src.agents.router import AgentRoute, route_turn
from src.observability import current_trace
from src.agents.tools import (
    competency_recommendation_tool,
    jev_resume_tool,
    rag_tool as retrieve_rag_tool,
    training_catalog_tool,
)
from src.dify_client import DifyClient
from src.jev_client import JevClient
from src.privacy import redact_text, sanitize
from src.response_synthesis import synthesize_response
from src.sql_tools import SkillGraphDatabase
from src.reasoning import agent_execution_steps, sanitize_steps
from src.resume_profile import extract_profile, render_profile


def run_agent_turn(
    message: str,
    *,
    conversation_state: dict[str, Any] | None = None,
    resume_text: str | None = None,
    has_resume: bool = False,
    trace: Any = None,
    ml_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = dict(conversation_state or {})
    try:
        validate_agent_input(message)
    except AgentGuardrailError as exc:
        return {
            "status": "blocked",
            "route": "guardrail",
            "answer": str(exc),
            "state_patch": {},
        }
    route = route_turn(message, has_resume=has_resume)
    active_trace = trace or current_trace()
    if active_trace:
        with active_trace.span(
            "crewai.core_router",
            "crewai",
            task_name="route_turn",
            metadata={"route": route.value, "has_resume": has_resume},
        ):
            pass
        trace = active_trace
    else:
        trace = None

    def _trace_tool(name: str, service: str, task_name: str, callback):
        if trace:
            with trace.span(name, service, task_name=task_name):
                return callback()
        return callback()
    if route == AgentRoute.SMALLTALK:
        return {
            "status": "local",
            "route": route.value,
            "answer": "Olá! Sou o SkillGraph. Posso ajudar com competências, trilhas, treinamentos e políticas de desenvolvimento.",
            "state_patch": {},
        }
    if route == AgentRoute.CLARIFY:
        return {
            "status": "clarify",
            "route": route.value,
            "answer": "Descreva um colaborador, uma competência, uma trilha, um treinamento ou uma política que deseja consultar.",
            "state_patch": {},
        }
    if os.getenv("CREWAI_ENABLED", "true").casefold() != "true":
        return {
            "status": "error",
            "route": route.value,
            "answer": "O sistema multiagente é obrigatório; configure CREWAI_ENABLED=true.",
            "error": "CREWAI_ENABLED deve ser true para executar a rota multiagente.",
            "state_patch": {"last_route": route.value},
        }
    try:
        artifact_path = Path(
            os.getenv(
                "SKILLGRAPH_ML_ARTIFACT",
                ".ml_artifacts/skillgraph_competency_tracks.pkl",
            )
        )
        database = None
        jev = JevClient(trace=trace) if route == AgentRoute.RESUME else None
        dify = None
        if route in {AgentRoute.TRAINING, AgentRoute.STRUCTURED}:
            database = SkillGraphDatabase(
                Path(os.getenv("SKILLGRAPH_DATA_DIR", "data_bd"))
            )
        if route == AgentRoute.RAG:
            dify = DifyClient.from_environment(trace=trace)

        def prediction_tool(profile_json: str) -> str:
            """Run the persisted competency PKL for a validated profile."""
            profile = json.loads(profile_json)
            skills = {
                item.get("normalized_name")
                or item["name"]: float(item.get("level") or 0)
                for item in profile.get("skills", [])
            }
            return json.dumps(
                _trace_tool(
                    "tool.competency_recommendation",
                    "ml",
                    "CompetencyRecommendationTool",
                    lambda: competency_recommendation_tool(artifact_path, skills),
                ),
                ensure_ascii=False,
            )

        def training_tool(competency: str = "") -> str:
            """Query the allowlisted training catalog only."""
            if database is None:
                raise RuntimeError("DuckDB não foi habilitado para esta rota.")
            return json.dumps(
                _trace_tool(
                    "tool.training_catalog",
                    "duckdb",
                    "TrainingCatalogTool",
                    lambda: training_catalog_tool(database, competency or None),
                ),
                ensure_ascii=False,
                default=str,
            )

        def competency_gap_tool() -> str:
            """Query aggregate competency gaps from read-only DuckDB."""
            if database is None:
                raise RuntimeError("DuckDB não foi habilitado para esta rota.")
            return json.dumps(
                _trace_tool(
                    "tool.competency_gap",
                    "duckdb",
                    "CompetencyGapTool",
                    lambda: database.competency_gap_breakdown(limit=10),
                ),
                ensure_ascii=False,
                default=str,
            )

        def rag_tool(question: str) -> str:
            """Retrieve competency and development evidence through Dify."""
            if dify is None:
                raise RuntimeError("Dify não foi habilitado para esta rota.")
            return json.dumps(
                _trace_tool(
                    "tool.rag",
                    "dify",
                    "DifyRagTool",
                    lambda: retrieve_rag_tool(dify, question),
                ),
                ensure_ascii=False,
                default=str,
            )


        tools = {
            "CompetencyRecommendationTool": prediction_tool,
            "TrainingCatalogTool": training_tool,
            "CompetencyGapTool": competency_gap_tool,
            "DifyRagTool": rag_tool,
        }
        if route == AgentRoute.ML and not ml_profile:
            raise RuntimeError("A rota de Machine Learning exige um perfil estruturado.")
        jev_result = {}
        resume_profile = None
        redacted_resume_text = ""
        if route == AgentRoute.RESUME:
            if jev is None:
                raise RuntimeError("JEV não foi habilitado para esta rota.")
            redacted_resume_text, redactions = redact_text(resume_text or "")
            redacted_resume_text = redacted_resume_text[:16000]
            questions = JevClient.load_questions(
                str(Path(__file__).parents[2] / "config" / "jev_resume_questions.json")
            )
            jev_response = jev_resume_tool(
                jev,
                {"document_text": redacted_resume_text, "purpose": "resume_extraction"},
                questions,
            )
            jev_result = sanitize({"response": jev_response, "redactions": redactions})
            resume_profile = extract_profile(redacted_resume_text, jev_result)
        crew = build_route_crew(route.value, tools=tools)
        result = crew.kickoff(
            inputs={
                "ml_profile": json.dumps(ml_profile or {}, ensure_ascii=False),

                "message": message,
                "resume_text": (
                    "[processed by structured extractor]" if resume_text else ""
                ),
                "resume_profile": (
                    resume_profile.model_dump_json() if resume_profile else ""
                ),
                "jev_result": json.dumps(jev_result, ensure_ascii=False),
                "profile_rendered": (
                    render_profile(resume_profile) if resume_profile else ""
                ),
                "review_result": "",
                "conversation_state": json.dumps(state, ensure_ascii=False),
            }
        )
        tasks_output = getattr(result, "tasks_output", None) or []
        core_output = tasks_output[0] if tasks_output else None
        reasoning_steps = agent_execution_steps(
            route.value,
            core_decision=core_output,
        )
        reasoning_steps = sanitize_steps(reasoning_steps)
        local_answer = str(result)
        rag_payload: dict[str, Any] = {}
        if route == AgentRoute.RAG:
            for output in tasks_output:
                candidate = getattr(output, "raw", output)
                if isinstance(candidate, str):
                    try:
                        candidate = json.loads(candidate)
                    except json.JSONDecodeError:
                        candidate = {}
                if isinstance(candidate, dict) and (candidate.get("answer") or candidate.get("sources")):
                    rag_payload = candidate
            if rag_payload.get("answer"):
                local_answer = str(rag_payload["answer"])
        final_answer, synthesis = synthesize_response(
            route.value,
            local_answer,
            structured_context={
                "profile_rendered": render_profile(resume_profile)
                if resume_profile
                else "",
                "profile": resume_profile.model_dump(mode="json")
                if resume_profile
                else None,
                "rag_answer": rag_payload.get("answer", ""),
                "rag_sources": rag_payload.get("sources", []),
                "state": sanitize(state),
            },
            sources=rag_payload.get("sources", []),
            trace=trace,
        )
        synthesis["fallback"] = False
        synthesis["provider"] = "gemini"
        return {
            "status": "completed",
            "route": route.value,
            "answer": final_answer,
            "profile": (
                resume_profile.model_dump(mode="json") if resume_profile else None
            ),
            "reasoning": sanitize_steps(reasoning_steps),
            "synthesis": {key: value for key, value in synthesis.items() if key != "error"},
            "state_patch": {"last_route": route.value},
        }
    except CrewAIUnavailable as exc:
        return {
            "status": "error",
            "route": route.value,
            "answer": f"O sistema multiagente não está disponível: {exc}",
            "error": str(exc),
            "state_patch": {"last_route": route.value},
        }
    except Exception as exc:
        public_error = str(exc)
        if "JEV" in public_error or "systemone" in public_error:
            answer = "A extração estruturada do currículo não foi concluída. Verifique a configuração ou a disponibilidade do JEV."
        elif (
            "Invalid response from LLM" in public_error
            or "None or empty" in public_error
        ):
            answer = "O modelo local não retornou uma resposta válida para esta etapa. Verifique o servidor e o modelo configurado."
        else:
            answer = "O fluxo especialista não pôde ser concluído. Verifique a configuração local."
        return {
            "status": "error",
            "route": route.value,
            "answer": answer,
            "error": public_error,
            "state_patch": {"last_route": route.value},
        }


def run_agent_flow(
    message: str,
    *,
    conversation_state: dict[str, Any] | None = None,
    resume_text: str | None = None,
    has_resume: bool = False,
    trace: Any = None,
) -> dict[str, Any]:
    return run_agent_turn(
        message,
        conversation_state=conversation_state,
        resume_text=resume_text,
        has_resume=has_resume,
        trace=trace,
    )
