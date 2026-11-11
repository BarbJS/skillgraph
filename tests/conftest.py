import pytest


class _TestGeminiSynthesizer:
    model = "gemini-test"

    def __init__(self, **kwargs):
        pass

    def synthesize(self, payload):
        return type(
            "Result",
            (),
            {
                "text": payload.get("draft_answer", ""),
                "model": self.model,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost": 0.0,
                "usage_source": "test",
                "cost_source": "test",
            },
        )()


@pytest.fixture(autouse=True)
def mock_mandatory_gemini_api(monkeypatch):
    """Keep mandatory synthesis tests deterministic without external API calls."""

    monkeypatch.setattr(
        "src.response_synthesis.GeminiSynthesizer", _TestGeminiSynthesizer
    )
    monkeypatch.setattr("src.gemini_synthesizer.GeminiSynthesizer", _TestGeminiSynthesizer)

    yield
