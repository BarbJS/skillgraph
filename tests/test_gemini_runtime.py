from src.agents.runtime import run_agent_turn
from src.gemini_synthesizer import GeminiSynthesisError


class FakeCrew:
    def kickoff(self, *, inputs):
        return type(
            "Result",
            (),
            {
                "tasks_output": [
                    {"intent": "training_recommendation", "reason": "ok"}
                ],
                "__str__": lambda self: "Rascunho local seguro.",
            },
        )()


class FakeGemini:
    model = "gemini-test"

    def __init__(self, **kwargs):
        pass

    def synthesize(self, payload):
        assert payload["draft_answer"] == "Rascunho local seguro."
        return type(
            "Result",
            (),
            {
                "text": "Resposta Gemini.",
                "model": self.model,
                "input_tokens": 10,
                "output_tokens": 6,
                "total_tokens": 16,
                "cost": 0.000022,
                "usage_source": "provider_reported",
                "cost_source": "configured_pricing",
            },
        )()


def test_runtime_requires_gemini_and_uses_its_answer(monkeypatch):
    monkeypatch.setenv("CREWAI_ENABLED", "true")
    monkeypatch.setattr(
        "src.agents.runtime.build_route_crew", lambda route, tools: FakeCrew()
    )
    monkeypatch.setattr(
        "src.response_synthesis.GeminiSynthesizer", FakeGemini
    )
    result = run_agent_turn("Quais treinamentos devo priorizar?")
    assert result["status"] == "completed"
    assert result["answer"] == "Resposta Gemini."
    assert result["synthesis"]["provider"] == "gemini"


def test_runtime_reports_gemini_failure_instead_of_faking_success(monkeypatch):
    monkeypatch.setenv("CREWAI_ENABLED", "true")
    monkeypatch.setattr(
        "src.agents.runtime.build_route_crew", lambda route, tools: FakeCrew()
    )

    class FailingGemini:
        model = "gemini-test"

        def __init__(self, **kwargs):
            pass

        def synthesize(self, payload):
            raise GeminiSynthesisError("Gemini indisponível")

    monkeypatch.setattr(
        "src.response_synthesis.GeminiSynthesizer", FailingGemini
    )
    result = run_agent_turn("Quais treinamentos devo priorizar?")
    assert result["status"] == "error"
    assert "Gemini" in result["error"]
