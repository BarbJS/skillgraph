"""Conversation-aware Core Router runtime for independent CrewAI routes."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from src.agents.crew import CrewAIUnavailable, build_route_crew
from src.agents.guardrails import AgentGuardrailError, validate_agent_input
from src.agents.router import AgentRoute, route_turn
from src.agents.tools import (
    comparison_tool,
    competency_lookup_tool,
    competency_recommendation_tool,
    jev_resume_tool,
    rag_tool as retrieve_rag_tool,
    training_catalog_tool,
)
from src.comparison import levels_in_question
from src.dify_client import DifyClient
from src.jev_client import JevClient
from src.observability import current_trace
from src.privacy import redact_text, sanitize
from src.reasoning import agent_execution_steps, sanitize_steps
from src.response_synthesis import synthesize_response
from src.resume_profile import extract_profile, render_profile
from src.sql_tools import SkillGraphDatabase


def _preserve_rag_answer(canonical: str, synthesized: str, payload: dict[str, Any]) -> str:
    """Keep Dify evidence when final wording drops supported facts."""
    canonical_text = str(canonical or "").strip()
    candidate = str(synthesized or "").strip()
    if not canonical_text:
        return candidate
    if not candidate:
        return canonical_text
    if any(marker in candidate.casefold() for marker in ("não encontrei", "nao encontrei", "não há informação", "nao ha informacao")):
        return canonical_text
    critical = set(re.findall(r"\b\d+(?:[,.]\d+)?%?\b", canonical_text))
    critical.update(
        token.casefold()
        for token in ("elegibilidade", "aprovação", "aprovacao", "gestor", "rh", "reembolso", "treinamento")
        if token in canonical_text.casefold()
    )
    if not critical.issubset(set(re.findall(r"\b\d+(?:[,.]\d+)?%?\b", candidate)) | {token for token in critical if token in candidate.casefold()}):
        return canonical_text
    return candidate


def _select_rag_payload(
    rag_cache: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return only the preloaded Dify payload for the RAG route."""
    return dict(rag_cache) if isinstance(rag_cache, dict) else {}



def _ml_deterministic_draft(profile: dict[str, Any], prediction: dict[str, Any]) -> str:
    """Build a dynamic, model-grounded ML draft before Gemini wording."""
    recommendations = prediction.get("recommendations") or []
    recognized = prediction.get("recognized_skills") or []
    unknown = prediction.get("unrecognized_skills") or []
    priorities = prediction.get("priorities") or []
    uncertainty = prediction.get("uncertainty") or {}
    tracks = "; ".join(
        f"{item.get('track', 'trilha não identificada')} ({float(item.get('compatibility', 0)):.0%})"
        for item in recommendations[:3]
    ) or "nenhuma trilha foi retornada pelo modelo"
    recognized_text = ", ".join(
        f"{item.get('input', item.get('feature', 'competência'))} (nível {item.get('level', 'não informado')})"
        for item in recognized[:8]
    ) or "nenhuma competência foi mapeada"
    unknown_text = ", ".join(str(item.get('input', 'competência')) for item in unknown[:8])
    priority_text = ", ".join(
        f"{item.get('skill', 'competência')} (lacuna {float(item.get('gap', 0)):.1f})"
        for item in priorities[:5]
    ) or "nenhuma prioridade calculada"
    answer = (
        f"Perfil analisado: {profile.get('employee_context', 'colaborador não identificado')}.\n\n"
        f"Trilhas retornadas pelo modelo: {tracks}.\n\n"
        f"Competências reconhecidas: {recognized_text}.\n\n"
        f"Prioridades de desenvolvimento: {priority_text}.\n\n"
        f"Incerteza: {uncertainty.get('level', 'não informada')}; cobertura do vocabulário: "
        f"{(prediction.get('input_quality') or {}).get('coverage', 'não informada')}."
    )
    if unknown_text:
        answer += (
            f"\n\nCompetências informadas que não estão no vocabulário do artefato atual: {unknown_text}. "
            "Isso não significa que elas não existam ou que o colaborador não as possua; elas não influenciaram o cálculo."
        )
    return answer


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
    route = route_turn(
        message,
        has_resume=has_resume,
        conversation_state=state,
    )
    if route == AgentRoute.BLOCKED:
        return {
            "status": "blocked",
            "route": route.value,
            "answer": "Não posso fornecer essas informações devido às restrições de segurança.",
            "state_patch": {},
        }
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
    if route == AgentRoute.ML and not ml_profile:
        return {
            "status": "clarify",
            "route": route.value,
            "answer": "Descreva as competências observadas de um colaborador e peça uma trilha ou prioridade de desenvolvimento.",
            "state_patch": {},
        }
    if route == AgentRoute.GAP and not state.get("prediction") and not state.get("employee_profile"):
        return {
            "status": "clarify",
            "route": route.value,
            "answer": "Informe as competências observadas ou envie um currículo antes de discutir lacunas.",
            "state_patch": {},
        }
    if route == AgentRoute.COMPARISON and len(levels_in_question(message)) < 2:
        return {
            "status": "clarify",
            "route": route.value,
            "answer": "Informe pelo menos dois níveis de cargo para comparar.",
            "state_patch": {},
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
        if route in {
            AgentRoute.TRAINING,
            AgentRoute.STRUCTURED,
            AgentRoute.COMPETENCY_LOOKUP,
        }:
            database = SkillGraphDatabase(
                Path(os.getenv("SKILLGRAPH_DATA_DIR", "data_bd"))
            )
        if route in {AgentRoute.RAG, AgentRoute.COMPARISON}:
            dify = DifyClient.from_environment(trace=trace)

        prediction_cache: str | None = None
        rag_cache: dict[str, Any] | None = None
        if route == AgentRoute.RAG:
            rag_cache = _trace_tool(
                "tool.rag",
                "dify",
                "DifyRagTool",
                lambda: retrieve_rag_tool(dify, message),
            )

        def prediction_tool(profile_json: str) -> str:
            """Run the persisted competency PKL exactly once for a validated profile."""
            nonlocal prediction_cache
            if prediction_cache is not None:
                return prediction_cache
            profile = json.loads(profile_json)
            raw_skills = profile.get("skills", {})
            if isinstance(raw_skills, Mapping):
                skills = {
                    str(name): float(level)
                    for name, level in raw_skills.items()
                }
            else:
                skills = {
                    item.get("normalized_name") or item["name"]: float(item.get("level") or 0)
                    for item in raw_skills
                }
            prediction_cache = json.dumps(
                _trace_tool(
                    "tool.competency_recommendation",
                    "ml",
                    "CompetencyRecommendationTool",
                    lambda: competency_recommendation_tool(artifact_path, skills),
                ),
                ensure_ascii=False,
            )
            return prediction_cache

        prediction_result: dict[str, Any] | None = None
        if route == AgentRoute.ML:
            prediction_result = json.loads(
                prediction_tool(json.dumps(ml_profile, ensure_ascii=False))
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
            """Retrieve Dify evidence using the user's exact original question."""
            nonlocal rag_cache
            if dify is None:
                raise RuntimeError("Dify não foi habilitado para esta rota.")
            if rag_cache is None:
                raise RuntimeError("A resposta canônica do Dify não foi carregada.")
            return json.dumps(rag_cache, ensure_ascii=False, default=str)

        def lookup_tool() -> str:
            """Run the allowlisted lookup for synthetic employee and competency IDs."""
            if database is None:
                raise RuntimeError("DuckDB não foi habilitado para esta rota.")
            employee = next(iter(re.findall(r"\bF\d{4}\b", message, re.IGNORECASE)), "")
            competency = next(iter(re.findall(r"\bCOMP\d{3}\b", message, re.IGNORECASE)), "")
            return json.dumps(
                _trace_tool(
                    "tool.competency_lookup",
                    "duckdb",
                    "CompetencyLookupTool",
                    lambda: competency_lookup_tool(database, employee.upper(), competency.upper()),
                ),
                ensure_ascii=False,
                default=str,
            )

        def comparison_tool_wrapper(question: str) -> str:
            """Run source-backed document comparison through the Dify tool."""
            if dify is None:
                raise RuntimeError("Dify não foi habilitado para esta rota.")
            return json.dumps(
                _trace_tool(
                    "tool.comparison",
                    "dify",
                    "ComparisonTool",
                    lambda: comparison_tool(dify, question),
                ),
                ensure_ascii=False,
                default=str,
            )

        tools = {
            "CompetencyRecommendationTool": prediction_tool,
            "TrainingCatalogTool": training_tool,
            "CompetencyGapTool": competency_gap_tool,
            "CompetencyLookupTool": lookup_tool,
            "ComparisonTool": comparison_tool_wrapper,
            "DifyRagTool": rag_tool,
        }
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
                "resume_text": "[processed by structured extractor]" if resume_text else "",
                "resume_profile": resume_profile.model_dump_json() if resume_profile else "",
                "jev_result": json.dumps(jev_result, ensure_ascii=False),
                "profile_rendered": render_profile(resume_profile) if resume_profile else "",
                "review_result": "",
                "conversation_state": json.dumps(state, ensure_ascii=False),
            }
        )
        tasks_output = getattr(result, "tasks_output", None) or []
        core_output = tasks_output[0] if tasks_output else None
        reasoning_steps = sanitize_steps(agent_execution_steps(route.value, core_decision=core_output))
        local_answer = "" if route == AgentRoute.RAG else str(result)
        table_rows: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        rag_payload: dict[str, Any] = (
            _select_rag_payload(rag_cache)
            if route == AgentRoute.RAG
            else {}
        )
        if route == AgentRoute.RAG and rag_payload.get("answer") and rag_payload.get("sources"):
            rag_payload["supported"] = True
        if rag_payload.get("answer"):
            local_answer = str(rag_payload["answer"])
        elif tasks_output and route != AgentRoute.RAG:
            candidate = getattr(tasks_output[-1], "raw", tasks_output[-1])
            if isinstance(candidate, dict) and candidate.get("answer"):
                local_answer = str(candidate["answer"])
        if route == AgentRoute.ML and prediction_result:
            local_answer = _ml_deterministic_draft(ml_profile or {}, prediction_result)
        if not local_answer.strip():
            local_answer = "O fluxo especialista foi concluído sem uma resposta textual."
        if isinstance(rag_payload.get("rows"), list):
            table_rows = rag_payload["rows"]
        if isinstance(rag_payload.get("sources"), list):
            sources = rag_payload["sources"]
        structured_context = {
            "profile_rendered": render_profile(resume_profile) if resume_profile else "",
            "profile": resume_profile.model_dump(mode="json") if resume_profile else None,
            "rag_answer": rag_payload.get("answer", ""),
            "rag_sources": rag_payload.get("sources", []),
            "prediction": prediction_result,
            "ml_profile": ml_profile,
            "state": sanitize(state),
        }
        if route == AgentRoute.RAG:
            final_answer = local_answer
            synthesis = {
                "provider": "dify",
                "preserved": True,
                "source_type": rag_payload.get("source_type", "dify"),
            }
        else:
            final_answer, synthesis = synthesize_response(
                route.value,
                local_answer,
                structured_context=structured_context,
                sources=sources,
                trace=trace,
            )

        synthesis["fallback"] = False
        if route != AgentRoute.RAG:
            synthesis["provider"] = "gemini"
        state_patch: dict[str, Any] = {"last_route": route.value}
        if ml_profile:
            state_patch["ml_profile"] = sanitize(ml_profile)
        if prediction_result:
            state_patch["prediction"] = sanitize(prediction_result)
        if resume_profile:
            state_patch["employee_profile"] = sanitize(resume_profile.model_dump(mode="json"))
        return {
            "status": "completed",
            "route": route.value,
            "answer": final_answer,
            "profile": resume_profile.model_dump(mode="json") if resume_profile else ml_profile,
            "structured": prediction_result,
            "table_rows": table_rows,
            "sources": sources,
            "reasoning": reasoning_steps,
            "synthesis": {key: value for key, value in synthesis.items() if key != "error"},
            "state_patch": state_patch,
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
        elif "Invalid response from LLM" in public_error or "None or empty" in public_error:
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
