from src.agents.crew import route_agent_roles
from src.agents.router import AgentRoute, route_turn
from src.agents.runtime import run_agent_turn


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
    assert result["status"] == "completed"
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
        "Response Synthesizer",
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
    assert result["status"] == "completed"
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
    assert result["status"] == "completed"
    assert result["route"] == "competency_development_rag"


class _PolicyFakeCrew(_FakeCrew):
    def kickoff(self, *, inputs):
        assert "DifyRagTool" in self.tools
        return super().kickoff(inputs=inputs)


def test_runtime_policy_wires_dify_tool(monkeypatch):
    monkeypatch.setenv("CREWAI_ENABLED", "true")
    monkeypatch.setenv("DIFY_API_KEY", "synthetic")
    monkeypatch.setattr(
        "src.agents.runtime.build_route_crew",
        lambda route, tools: _PolicyFakeCrew(route, tools),
    )
    result = run_agent_turn("Quais regras de reembolso se aplicam?")
    assert result["status"] == "completed"
    assert result["route"] == "competency_development_rag"
    assert any(
        step.get("tool") == "DifyRagTool" for step in result["reasoning"]
    )
