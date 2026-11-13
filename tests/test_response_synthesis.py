from src.response_synthesis import synthesize_response


def test_response_synthesis_sends_sanitized_context(monkeypatch):
    calls = []

    class FakeGemini:
        model = "gemini-test"

        def __init__(self, **kwargs):
            pass

        def synthesize(self, payload):
            calls.append(payload)
            return type(
                "Result",
                (),
                {
                    "text": "Resposta final",
                    "model": "gemini-test",
                    "input_tokens": 3,
                    "output_tokens": 2,
                    "total_tokens": 5,
                    "cost": 0.01,
                    "usage_source": "provider_reported",
                    "cost_source": "configured_pricing",
                },
            )()

    monkeypatch.setattr("src.response_synthesis.GeminiSynthesizer", FakeGemini)
    text, metadata = synthesize_response(
        "competency_development_rag",
        "rascunho",
        structured_context={
            "resume_text": "não enviar",
            "safe": "ok",
        },
    )
    assert text == "Resposta final"
    assert metadata["input_tokens"] == 3
    assert "resume_text" not in str(calls[0])
    assert "não enviar" not in str(calls[0])
