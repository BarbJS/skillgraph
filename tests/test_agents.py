from pathlib import Path

from src.agents.crew import CrewAIUnavailable, build_skillgraph_crew
from src.agents.flow import AgentFlowState
from src.agents.schemas import EmployeeProfile, SkillEvidence


def test_agent_flow_context_is_json_serializable():
    state = AgentFlowState(
        employee_profile=EmployeeProfile(skills=[SkillEvidence(name="Python", level=4)])
    )
    context = state.as_context()
    assert context["employee_profile"]["skills"][0]["level"] == 4.0


def test_crewai_requires_explicit_runtime_when_disabled(monkeypatch):
    monkeypatch.setenv("CREWAI_ENABLED", "false")
    try:
        build_skillgraph_crew()
    except CrewAIUnavailable as exc:
        assert "desativado" in str(exc)
    else:
        raise AssertionError("CrewAI should reject a disabled configuration")


def test_all_agent_prompts_exist():
    prompt_dir = Path(__file__).parents[1] / "src" / "agents" / "prompts"
    expected = {
        "core",
        "resume_interpreter",
        "profile",
        "prediction",
        "gap",
        "training",
        "rag_specialist",
        "reviewer",
        "synthesizer",
    }
    assert {path.stem for path in prompt_dir.glob("*.md")} >= expected
