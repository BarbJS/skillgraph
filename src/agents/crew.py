"""CrewAI route-specific crews with Core Router handoffs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class CrewAIUnavailable(RuntimeError):
    pass


def _llm():
    from crewai import LLM

    return LLM(
        model=os.getenv("CREWAI_LLM_MODEL", "openai/meta-llama-3-8b-instruct"),
        base_url=os.getenv("CREWAI_LLM_BASE_URL", "http://127.0.0.1:1234/v1"),
        api_key=os.getenv("CREWAI_LLM_API_KEY", "lm-studio-local"),
        temperature=0,
    )


def _load_crewai():
    if os.getenv("CREWAI_ENABLED", "false").casefold() != "true":
        raise CrewAIUnavailable(
            "CrewAI está desativado; configure CREWAI_ENABLED=true."
        )
    try:
        from crewai import Agent, Crew, Process, Task
        from crewai.tools import tool

        return Agent, Crew, Process, Task, tool
    except ImportError as exc:
        raise CrewAIUnavailable(
            "CrewAI não está disponível no ambiente oficial. Execute make bootstrap-crewai e make run."
        ) from exc


def crewai_installation_hint() -> str:
    return "Use: make bootstrap-crewai && make run"


def crewai_is_available() -> bool:
    try:
        import crewai  # noqa: F401

        return True
    except ImportError:
        return False


def crewai_runtime_path() -> str:
    return os.getenv("CREWAI_PYTHON", ".venv/bin/python")


def _load_crewai_from_venv():
    """Document the required runtime without unsafe dynamic interpreter loading."""
    return _load_crewai()


_ROUTE_SPECIALISTS: dict[str, tuple[tuple[str, str, str, tuple[str, ...]], ...]] = {
    "resume_analysis": (
        (
            "Resume Interpreter",
            "resume_interpreter",
            "Extrair evidências profissionais sem inventar dados.",
            (),
        ),
        ("Profile Normalizer", "profile", "Normalizar um perfil validado.", ()),
    ),
    "ml_prediction": (
        (
            "Prediction Specialist",
            "prediction",
            "Executar a recomendação PKL/XAI.",
            ("CompetencyRecommendationTool",),
        ),
    ),
    "gap_analysis": (
        ("Gap Analyst", "gap", "Interpretar prioridades e lacunas sem inventar.", ()),
    ),
    "training_recommendation": (
        (
            "Learning Path & Training Recommendation Agent",
            "training",
            "Selecionar treinamentos existentes e pré-requisitos; nunca treinar o modelo.",
            ("TrainingCatalogTool",),
        ),
    ),
    "policy_rag": (
        (
            "Policy Specialist",
            "policy",
            "Consultar políticas com fontes.",
            ("DifyPolicyTool",),
        ),
    ),
    "structured_data": (
        (
            "Structured Data Specialist",
            "training",
            "Consultar somente dados estruturados autorizados.",
            ("TrainingCatalogTool",),
        ),
    ),
}


def route_agent_roles(route: str) -> tuple[str, ...]:
    """Return the exact agent roles used by one selected route."""

    specialists = _ROUTE_SPECIALISTS.get(route)
    if specialists is None:
        raise ValueError(f"Rota CrewAI não suportada: {route}")
    return (
        "Core Router",
        *(item[0] for item in specialists),
        "Safety Reviewer",
        "Response Synthesizer",
    )


def build_route_crew(
    route: str,
    *,
    prompts_dir: Path | None = None,
    tools: dict[str, object] | None = None,
):
    """Build the Core-led specialist chain for one selected route."""

    Agent, Crew, Process, Task, tool = _load_crewai()
    specialist_specs = _ROUTE_SPECIALISTS.get(route)
    if specialist_specs is None:
        raise ValueError(f"Rota CrewAI não suportada: {route}")

    root = prompts_dir or Path(__file__).parent / "prompts"
    model = _llm()
    configured = tools or {}
    reasoning_enabled = (
        os.getenv("CREWAI_AGENT_REASONING", "false").casefold() == "true"
    )
    max_iter = max(1, int(os.getenv("CREWAI_AGENT_MAX_ITER", "2")))
    max_retries = max(0, int(os.getenv("CREWAI_AGENT_MAX_RETRIES", "1")))
    execution_timeout = max(1, int(os.getenv("CREWAI_AGENT_TIMEOUT_SECONDS", "180")))

    def prompt(name: str) -> str:
        return (root / f"{name}.md").read_text(encoding="utf-8")

    def agent(role: str, name: str, goal: str, allowed: tuple[str, ...] = ()):
        selected = [tool(key)(configured[key]) for key in allowed if key in configured]
        return Agent(
            role=role,
            goal=goal,
            backstory=prompt(name),
            allow_delegation=False,
            reasoning=reasoning_enabled,
            max_iter=max_iter,
            max_reasoning_attempts=2 if reasoning_enabled else None,
            max_retry_limit=max_retries,
            max_execution_time=execution_timeout,
            llm=model,
            function_calling_llm=model,
            tools=selected,
        )

    core = agent(
        "Core Router",
        "core",
        "Orquestrar a rota selecionada e coordenar os handoffs com segurança.",
    )
    reviewer = agent(
        "Safety Reviewer", "reviewer", "Revisar segurança, evidências e escopo."
    )
    synthesizer = agent(
        "Response Synthesizer",
        "synthesizer",
        "Redigir a resposta final baseada nos JSONs revisados.",
    )

    tasks: list[Any] = [
        Task(
            description=(
                "Você é o orquestrador obrigatório deste turno. Confirme a rota candidata "
                f"'{route}', leia a mensagem e o estado estruturado, escolha o próximo agente "
                "permitido e produza um handoff JSON curto. Não execute ferramentas. "
                "Mensagem: {message}\nEstado: {conversation_state}"
            ),
            expected_output="Handoff JSON do Core Router",
            agent=core,
        )
    ]

    for role, prompt_name, goal, allowed in specialist_specs:
        specialist = agent(role, prompt_name, goal, allowed)
        if role == "Resume Interpreter":
            description = (
                "O backend já extraiu e validou o perfil completo em {resume_profile} e renderizou "
                "a lista obrigatória em {profile_rendered}. Preserve todos os itens, níveis, confiança, "
                "evidências e unrecognized_skills. Use o JEV em {jev_result} somente como sinais "
                "complementares. Não substitua a lista por um resumo, não invente informações e devolva "
                "um handoff que mantenha todo o EmployeeProfile."
            )
        elif role == "Profile Normalizer":
            description = (
                "Normalize somente o EmployeeProfile anterior; preserve todas as competências, "
                "unrecognized_skills, evidências, confiança e níveis incertos; remova PII."
            )
        elif role == "Prediction Specialist":
            description = "Use somente a ferramenta PKL/XAI permitida no perfil estruturado do estado."
        elif role == "Gap Analyst":
            description = "Analise somente prediction e employee_profile disponíveis e devolva lacunas estruturadas."
        elif role == "Learning Path & Training Recommendation Agent":
            description = "Consulte somente o catálogo DuckDB allowlisted para as prioridades do estado."
        elif role == "Policy Specialist":
            description = "Consulte a política somente pelo Dify e preserve fontes e ausência de evidência."
        else:
            description = "Execute somente a consulta read-only permitida para o indicador solicitado."
        tasks.append(
            Task(
                description=description,
                expected_output=f"Handoff estruturado de {role}",
                agent=specialist,
            )
        )

    tasks.append(
        Task(
            description=(
                "Revise o perfil normalizado e os sinais JEV quanto a PII, escopo, evidências "
                "e incerteza. Retorne ReviewResult JSON; não substitua o perfil nem apague a lista "
                "de competências."
            ),
            expected_output="ReviewResult JSON",
            agent=reviewer,
        )
    )
    tasks.append(
        Task(
            description=(
                "Redija a resposta final em português usando o perfil_rendered canônico e a revisão recebida. "
                "Apresente todas as competências/habilidades reconhecidas com nível de senioridade de "
                "0 a 5 ou não determinável, confiança e evidência curta. Liste explicitamente todas as "
                "competências não reconhecidas ou com nível incerto. NÃO inclua sinais, campos, nomes, "
                "scores ou respostas do JEV na resposta final; esses dados são internos do backend. "
                "Não invente traduções, siglas ou atribuições. Não responda apenas com warnings.\n"
                "Lista canônica obrigatória:\n{profile_rendered}\n"
                "Perfil estruturado:\n{resume_profile}\n"
                "Revisão:\n{review_result}\n"
            ),
            expected_output="Resposta final com competências, níveis, evidências e incerteza",
            agent=synthesizer,
        )
    )

    core_task = tasks[0]
    specialist_tasks = tasks[1:-2]
    reviewer_task = tasks[-2]
    synthesizer_task = tasks[-1]
    for index, task in enumerate(specialist_tasks):
        task.context = [core_task] if index == 0 else [specialist_tasks[index - 1]]
    if route == "resume_analysis" and len(specialist_tasks) >= 2:
        reviewer_task.context = [specialist_tasks[-1], specialist_tasks[-2]]
        synthesizer_task.context = [
            reviewer_task,
            specialist_tasks[-1],
            specialist_tasks[-2],
        ]
    else:
        reviewer_task.context = [
            specialist_tasks[-1] if specialist_tasks else core_task
        ]
        synthesizer_task.context = [
            reviewer_task,
            specialist_tasks[-1] if specialist_tasks else core_task,
        ]

    return Crew(
        agents=[task.agent for task in tasks],
        tasks=tasks,
        process=Process.sequential,
        verbose=False,
    )


def build_skillgraph_crew(
    *, prompts_dir: Path | None = None, tools: dict[str, object] | None = None
):
    """Compatibility builder: the Core Router orchestrates the ML route."""
    return build_route_crew("ml_prediction", prompts_dir=prompts_dir, tools=tools)
