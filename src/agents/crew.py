"""CrewAI route-specific crews with Core Router handoffs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class CrewAIUnavailable(RuntimeError):
    pass


def _llm():
    from crewai import LLM
    return LLM(model=os.getenv("CREWAI_LLM_MODEL", "openai/meta-llama-3-8b-instruct"), base_url=os.getenv("CREWAI_LLM_BASE_URL", "http://127.0.0.1:1234/v1"), api_key=os.getenv("CREWAI_LLM_API_KEY", "lm-studio-local"), temperature=0)


def _load_crewai():
    if os.getenv("CREWAI_ENABLED", "false").casefold() != "true":
        raise CrewAIUnavailable("CrewAI está desativado; configure CREWAI_ENABLED=true.")
    try:
        from crewai import Agent, Crew, Process, Task
        from crewai.tools import tool
        return Agent, Crew, Process, Task, tool
    except ImportError as exc:
        raise CrewAIUnavailable("Instale CrewAI no .crew-venv antes de ativar a crew.") from exc


def build_route_crew(route: str, *, prompts_dir: Path | None = None, tools: dict[str, object] | None = None):
    """Build only the specialist route selected by the Core Router.

    The specialist returns to the Core through the structured crew result. A
    Reviewer and Synthesizer close each route; unrelated tools are not exposed.
    """
    Agent, Crew, Process, Task, tool = _load_crewai()
    root = prompts_dir or Path(__file__).parent / "prompts"
    model = _llm()
    configured = tools or {}
    def prompt(name: str) -> str:
        return (root / f"{name}.md").read_text(encoding="utf-8")
    def agent(role: str, name: str, goal: str, allowed: tuple[str, ...] = ()):
        selected = [tool(key)(configured[key]) for key in allowed if key in configured]
        return Agent(role=role, goal=goal, backstory=prompt(name), allow_delegation=False, reasoning=True, max_iter=4, max_reasoning_attempts=2, llm=model, tools=selected)

    core = agent("Core Router", "core", "Classificar e encaminhar a intenção com segurança.")
    reviewer = agent("Safety Reviewer", "reviewer", "Revisar segurança, evidências e escopo.")
    synthesizer = agent("Response Synthesizer", "synthesizer", "Redigir a resposta final baseada nos JSONs revisados.")
    tasks: list[Any] = [Task(description="Classifique a intenção da mensagem e preserve o estado JSON: {message} / {conversation_state}.", expected_output="JSON de rota", agent=core)]

    if route == "resume_analysis":
        specialist = agent("Resume Interpreter", "resume_interpreter", "Extrair evidências profissionais sem inventar dados.", ("JevResumeExtractionTool",))
        profile = agent("Profile Normalizer", "profile", "Normalizar um perfil validado.")
        tasks.extend([
            Task(description="Analise o texto do currículo com a ferramenta permitida e devolva evidências JSON: {resume_text}.", expected_output="Perfil de currículo JSON", agent=specialist),
            Task(description="Normalize o perfil anterior, preserve desconhecidos e remova PII.", expected_output="EmployeeProfile JSON", agent=profile),
        ])
    elif route == "ml_prediction":
        specialist = agent("Prediction Specialist", "prediction", "Executar a recomendação PKL/XAI.", ("CompetencyRecommendationTool",))
        tasks.append(Task(description="Use o perfil estruturado do estado e invoque apenas o PKL/XAI.", expected_output="PredictionResult JSON", agent=specialist))
    elif route == "gap_analysis":
        specialist = agent("Gap Analyst", "gap", "Interpretar prioridades e lacunas sem inventar.")
        tasks.append(Task(description="Analise prediction e employee_profile do estado; retorne lacunas estruturadas.", expected_output="Gap JSON", agent=specialist))
    elif route == "learning_recommendation":
        specialist = agent("Learning Path & Training Recommendation Agent", "training", "Selecionar treinamentos existentes e pré-requisitos; nunca treinar o modelo.", ("TrainingCatalogTool",))
        tasks.append(Task(description="Consulte somente o catálogo DuckDB allowlisted para as prioridades do estado.", expected_output="Training JSON", agent=specialist))
    elif route == "policy_rag":
        specialist = agent("Policy Specialist", "policy", "Consultar políticas com fontes.", ("DifyPolicyTool",))
        tasks.append(Task(description="Consulte a política solicitada somente pelo Dify e preserve fontes.", expected_output="PolicyEvidence JSON", agent=specialist))
    elif route == "structured_data":
        specialist = agent("Structured Data Specialist", "training", "Consultar somente dados estruturados autorizados.", ("TrainingCatalogTool",))
        tasks.append(Task(description="Execute a função read-only adequada para o indicador solicitado.", expected_output="Structured JSON", agent=specialist))
    else:
        raise ValueError(f"Rota CrewAI não suportada: {route}")

    tasks.append(Task(description="Revise todos os JSONs anteriores, PII, escopo, evidências e incerteza.", expected_output="ReviewResult JSON", agent=reviewer))
    tasks.append(Task(description="Redija a resposta final em português usando apenas os JSONs revisados. Retorne ao Core.", expected_output="Resposta final", agent=synthesizer))
    for index in range(1, len(tasks)):
        tasks[index].context = tasks[:index]
    return Crew(agents=[task.agent for task in tasks], tasks=tasks, process=Process.sequential, verbose=False)


def build_skillgraph_crew(*, prompts_dir: Path | None = None, tools: dict[str, object] | None = None):
    """Compatibility builder: the Core Router chooses a route at runtime."""
    return build_route_crew("ml_prediction", prompts_dir=prompts_dir, tools=tools)
