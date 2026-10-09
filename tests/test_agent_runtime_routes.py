from src.agents.crew import route_agent_roles
from src.agents.router import AgentRoute, route_turn
from src.agents.runtime import run_agent_turn


def test_training_and_policy_messages_use_agent_routes():
    assert route_turn("Quais treinamentos devo priorizar?") is AgentRoute.TRAINING
    assert route_turn("Quais regras de reembolso se aplicam?") is AgentRoute.POLICY


def test_training_and_policy_roles_are_least_privilege():
    assert route_agent_roles("training_recommendation") == (
        "Core Router",
        "Learning Path & Training Recommendation Agent",
        "Safety Reviewer",
        "Response Synthesizer",
    )
    assert route_agent_roles("policy_rag") == (
        "Core Router",
        "Policy Specialist",
        "Safety Reviewer",
        "Response Synthesizer",
    )


def test_runtime_reports_disabled_route_without_calling_external_services(monkeypatch):
    monkeypatch.delenv("CREWAI_ENABLED", raising=False)
    result = run_agent_turn("Quais treinamentos devo priorizar?")
    assert result["status"] == "disabled"
    assert result["route"] == "training_recommendation"


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
        assert "TrainingCatalogTool" in self.tools or "DifyPolicyTool" in self.tools
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
    assert result["route"] == "policy_rag"


class _PolicyFakeCrew(_FakeCrew):
    def kickoff(self, *, inputs):
        assert "DifyPolicyTool" in self.tools
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
    assert result["route"] == "policy_rag"
    assert any(
        step.get("tool") == "DifyPolicyTool" for step in result["reasoning"]
    )
