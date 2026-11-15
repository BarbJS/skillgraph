from src.agents.crew import build_route_crew, route_agent_roles
from src.agents.router import AgentRoute, route_turn
from src.agents.runtime import _select_rag_payload, run_agent_turn


def test_rag_crew_wires_specialist_into_safety_reviewer(monkeypatch):
    class FakeAgent:
        def __init__(self, **kwargs):
            self.role = kwargs["role"]

    class FakeTask:
        def __init__(self, *, description, expected_output, agent):
            self.description = description
            self.expected_output = expected_output
            self.agent = agent
            self.context = None

    class FakeCrew:
        def __init__(self, *, agents, tasks, process, verbose):
            self.agents = agents
            self.tasks = tasks

    class FakeProcess:
        sequential = "sequential"

    def fake_tool(_name):
        return lambda function: function

    monkeypatch.setattr(
        "src.agents.crew._load_crewai",
        lambda: (FakeAgent, FakeCrew, FakeProcess, FakeTask, fake_tool),
    )
    monkeypatch.setattr("src.agents.crew._llm", lambda: object())

    crew = build_route_crew(
        "competency_development_rag",
        tools={"DifyRagTool": lambda question: question},
    )

    assert [agent.role for agent in crew.agents] == [
        "Core Router",
        "Competency & Development Specialist",
        "Safety Reviewer",
    ]
    assert crew.tasks[1].context == [crew.tasks[0]]
    assert crew.tasks[2].context == [crew.tasks[1]]


def test_rag_payload_prefers_direct_dify_result_over_review_paraphrase():
    tasks = [
        {"intent": "competency_development_rag"},
        {"answer": "Resposta completa do especialista.", "sources": [{"document": "politica_treinamentos.md"}]},
        {"answer": "Resumo incorreto do revisor.", "sources": [{"document": "politica_treinamentos.md"}]},
    ]
    direct = {"answer": "Resposta completa retornada pelo Dify.", "sources": [{"document": "politica_treinamentos.md"}]}

    assert _select_rag_payload(tasks, direct) == direct


def test_rag_payload_ignores_reviewer_when_direct_result_is_unavailable():
    tasks = [
        {"intent": "competency_development_rag"},
        {"answer": "Resposta completa do especialista.", "sources": [{"document": "politica_treinamentos.md"}]},
        {"answer": "Resumo incorreto do revisor.", "sources": [{"document": "politica_treinamentos.md"}]},
    ]

    assert _select_rag_payload(tasks, None)["answer"] == "Resposta completa do especialista."


class _RagExactQueryCrew:
    def __init__(self, tools):
        self.tools = tools

    def kickoff(self, *, inputs):
        payload = self.tools["DifyRagTool"]("paráfrase criada pelo agente")
        return type(
            "Result",
            (),
            {
                "tasks_output": [
                    {"intent": "competency_development_rag"},
                    {"raw": payload},
                    {"raw": '{"answer":"Resumo incorreto do revisor.","sources":[{"document":"politica_treinamentos.md"}]}'},
                ],
                "__str__": lambda self: "Resposta não estruturada",
            },
        )()


def test_rag_runtime_uses_exact_original_question_and_direct_payload(monkeypatch):
    monkeypatch.setenv("CREWAI_ENABLED", "true")
    monkeypatch.setenv("DIFY_API_KEY", "synthetic")
    calls = []

    def fake_retrieve(client, question):
        calls.append(question)
        return {
            "answer": "Resposta completa do Dify.",
            "sources": [{"document": "politica_treinamentos.md"}],
            "supported": True,
            "source_type": "dify",
        }

    monkeypatch.setattr("src.agents.runtime.retrieve_rag_tool", fake_retrieve)
    monkeypatch.setattr(
        "src.agents.runtime.build_route_crew",
        lambda route, tools: _RagExactQueryCrew(tools),
    )

    result = run_agent_turn("pergunta original")

    assert result["status"] == "completed"
    assert result["answer"] == "Resposta completa do Dify."
    assert calls == ["pergunta original"]
    assert result["synthesis"]["provider"] == "dify"


def test_training_policy_and_gap_messages_use_agent_routes():
    assert route_turn("Quais treinamentos devo priorizar?") is AgentRoute.TRAINING
    assert route_turn("Quais regras de reembolso se aplicam?") is AgentRoute.RAG
    assert route_turn("Quais competências têm mais lacunas?") is AgentRoute.STRUCTURED


def test_documentary_training_rules_use_general_rag_specialist():
    assert (
        route_turn("Treinamentos online contam para a carga horária anual?")
        is AgentRoute.RAG
    )
    assert route_turn("Qual é o prazo para concluir um treinamento obrigatório?") is AgentRoute.RAG


def test_training_catalog_questions_use_training_specialist():
    assert route_turn("Quais treinamentos estão disponíveis?") is AgentRoute.TRAINING
    assert route_turn("Quais cursos existem no catálogo?") is AgentRoute.TRAINING


def test_runtime_structured_route_wires_gap_tool(monkeypatch):
    monkeypatch.setenv("CREWAI_ENABLED", "true")
    monkeypatch.setattr(
        "src.agents.runtime.build_route_crew",
        lambda route, tools: _FakeCrew(route, tools),
    )
    result = run_agent_turn("Quais competências têm mais lacunas?")
    assert result["status"] in {"completed", "error"}
    assert result["route"] == "structured_data"
    assert any(step.get("tool") == "CompetencyGapTool" for step in result["reasoning"])


def test_training_and_policy_roles_are_least_privilege():
    assert route_agent_roles("training_recommendation") == (
        "Core Router",
        "Learning Path & Training Recommendation Agent",
        "Safety Reviewer",
        "Response Synthesizer",
    )
    assert route_agent_roles("competency_development_rag") == (
        "Core Router",
        "Competency & Development Specialist",
        "Safety Reviewer",
    )


def test_runtime_requires_crewai_for_domain_routes(monkeypatch):
    monkeypatch.setenv("CREWAI_ENABLED", "false")
    result = run_agent_turn("Quais treinamentos devo priorizar?")
    assert result["status"] == "error"
    assert result["route"] == "training_recommendation"
    assert "obrigatório" in result["answer"]


def test_runtime_uses_training_tool_and_trace(monkeypatch):
    monkeypatch.setenv("CREWAI_ENABLED", "true")
    monkeypatch.setattr(
        "src.agents.runtime.build_route_crew",
        lambda route, tools: _FakeCrew(route, tools),
    )
    result = run_agent_turn("Quais treinamentos devo priorizar?")
    assert result["status"] in {"completed", "error"}
    assert result["route"] == "training_recommendation"
    assert result["reasoning"][-2]["stage"] == "Safety Reviewer"
    assert result["reasoning"][-1]["stage"] == "Response Synthesizer"


class _FakeCrew:
    def __init__(self, route, tools):
        self.route = route
        self.tools = tools

    def kickoff(self, *, inputs):
        assert "TrainingCatalogTool" in self.tools or "DifyRagTool" in self.tools
        return type(
            "Result",
            (),
            {
                "tasks_output": [
                    {
                        "intent": self.route,
                        "next_agent": "specialist",
                        "reason": "ok",
                        "validation": "ok",
                    }
                ]
            },
        )()


def test_runtime_uses_policy_tool(monkeypatch):
    monkeypatch.setenv("CREWAI_ENABLED", "true")
    monkeypatch.setenv("DIFY_API_KEY", "synthetic")
    monkeypatch.setattr(
        "src.agents.runtime.build_route_crew",
        lambda route, tools: _FakeCrew(route, tools),
    )
    result = run_agent_turn("Quais regras de reembolso se aplicam?")
    assert result["status"] in {"completed", "error"}
    assert result["route"] == "competency_development_rag"


class _PolicyFakeCrew(_FakeCrew):
    def kickoff(self, *, inputs):
        assert "DifyRagTool" in self.tools
        return super().kickoff(inputs=inputs)


class _RagResult:
    tasks_output = [
        type("Output", (), {"raw": '{"answer":"Treinamentos online valem horas.","sources":[{"document":"faq_desenvolvimento.md","content":"Cursos online valem horas."}]}'})()
    ]

    def __str__(self):
        return "RAG answer: Treinamentos online valem horas."


class _RagFakeCrew(_PolicyFakeCrew):
    def kickoff(self, *, inputs):
        assert "DifyRagTool" in self.tools
        return _RagResult()


def test_rag_runtime_preserves_answer_and_sources(monkeypatch):
    monkeypatch.setenv("CREWAI_ENABLED", "true")
    monkeypatch.setenv("DIFY_API_KEY", "synthetic")
    monkeypatch.setattr(
        "src.agents.runtime.build_route_crew",
        lambda route, tools: _RagFakeCrew(route, tools),
    )
    result = run_agent_turn("Treinamentos online contam para a carga horária anual?")
    assert result["status"] in {"completed", "error"}
    assert result["answer"] != ""
    assert "EmployeeProfile" not in result["answer"]
    assert result["route"] == "competency_development_rag"


def test_runtime_policy_wires_dify_tool(monkeypatch):
    monkeypatch.setenv("CREWAI_ENABLED", "true")
    monkeypatch.setenv("DIFY_API_KEY", "synthetic")
    monkeypatch.setattr(
        "src.agents.runtime.build_route_crew",
        lambda route, tools: _PolicyFakeCrew(route, tools),
    )
    result = run_agent_turn("Quais regras de reembolso se aplicam?")
    assert result["status"] in {"completed", "error"}
    assert result["route"] == "competency_development_rag"
    assert any(
        step.get("tool") == "DifyRagTool" for step in result["reasoning"]
    )
