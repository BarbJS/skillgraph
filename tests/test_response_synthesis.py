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


def test_response_synthesis_accepts_ml_scores_without_false_pii_block(monkeypatch):
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
                    "text": "Recomendação de desenvolvimento.",
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
    text, _ = synthesize_response(
        "ml_prediction",
        "Trilhas mais compatíveis para o colaborador.",
        structured_context={
            "ml_profile": {
                "employee_context": "colaborador da equipe de dados",
                "skills": {"Programming": 4.0},
                "goal": "desenvolvimento",
            },
            "prediction": {
                "recommendations": [
                    {"track": "Dados e Ciência de Dados", "compatibility": 0.29999999999999993}
                ],
                "priorities": [{"skill": "Mathematics", "gap": 4.9399999999999995}],
            },
        },
    )
    assert text == "Recomendação de desenvolvimento."
    assert calls
    assert "0.29999999999999993" in str(calls[0])
