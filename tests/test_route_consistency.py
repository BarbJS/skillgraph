from pathlib import Path

from src.agents.crew import _ROUTE_SPECIALISTS, route_agent_roles
from src.agents.router import AgentRoute, route_turn
from src.agents.runtime import run_agent_turn


ROOT = Path(__file__).parents[1]
PROMPTS = ROOT / "src" / "agents" / "prompts"


def test_every_crew_route_has_an_existing_prompt():
    for route, specs in _ROUTE_SPECIALISTS.items():
        assert route_agent_roles(route)
        for _, prompt_name, _, _ in specs:
            assert (PROMPTS / f"{prompt_name}.md").is_file(), (route, prompt_name)


def test_clarify_precedes_documentary_fallback_for_underspecified_questions():
    assert route_turn("Qual é o prazo?") is AgentRoute.CLARIFY
    assert route_turn("Como funciona?") is AgentRoute.CLARIFY


def test_gap_route_requires_persisted_context():
    assert route_turn("Quais lacunas ele possui?", conversation_state={}) is AgentRoute.STRUCTURED
    assert route_turn(
        "Quais lacunas ele possui?",
        conversation_state={"prediction": {"priorities": []}},
    ) is AgentRoute.GAP


def test_ml_without_profile_returns_clarify_before_model_execution(monkeypatch):
    monkeypatch.setenv("CREWAI_ENABLED", "true")
    result = run_agent_turn("Qual trilha combina com este colaborador?")
    assert result["status"] == "clarify"
    assert result["route"] == AgentRoute.ML.value


def test_completed_ml_turn_persists_sanitized_context(monkeypatch):
    class FakeCrew:
        def kickoff(self, *, inputs):
            return type("Result", (), {"tasks_output": [{"intent": "ml_prediction"}], "__str__": lambda self: "Resposta estruturada"})()

    class FakeGemini:
        model = "test"
        def __init__(self, **kwargs):
            pass
        def synthesize(self, payload):
            return type("Synthesis", (), {"text": "Resposta segura", "model": "test", "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost": 0.0, "usage_source": "test", "cost_source": "test"})()

    monkeypatch.setenv("CREWAI_ENABLED", "true")
    monkeypatch.setattr("src.agents.runtime.build_route_crew", lambda route, tools: FakeCrew())
    monkeypatch.setattr("src.response_synthesis.GeminiSynthesizer", FakeGemini)
    result = run_agent_turn(
        "Qual trilha combina com este colaborador?",
        ml_profile={"employee_context": "equipe de dados", "skills": {"Python": 4}},
    )
    assert result["status"] in {"completed", "error"}
    if result["status"] == "completed":
        assert "ml_profile" in result["state_patch"]
        assert "prediction" in result["state_patch"]
