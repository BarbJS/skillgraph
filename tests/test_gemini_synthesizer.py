from src.gemini_synthesizer import GeminiSynthesisError, GeminiSynthesizer


class Response:
    status_code = 200

    def json(self):
        return {
            "candidates": [{"content": {"parts": [{"text": "Resposta final."}]}}],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 6,
                "totalTokenCount": 16,
            },
        }


class Session:
    def __init__(self):
        self.calls = []

    def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return Response()


def test_gemini_defaults_to_current_flash_model(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    client = GeminiSynthesizer(enabled=False, api_key="key", session=Session())
    assert client.model == "gemini-3.1-flash-lite"


def test_gemini_defaults_to_one_attempt_without_fallback(monkeypatch):
    monkeypatch.delenv("GEMINI_MAX_ATTEMPTS", raising=False)
    monkeypatch.delenv("GEMINI_ALLOW_FALLBACK", raising=False)
    client = GeminiSynthesizer(enabled=False, api_key="key", session=Session())
    assert client.max_attempts == 1
    assert client.allow_fallback is False


def test_disabled_gemini_does_not_call_api():
    session = Session()
    client = GeminiSynthesizer(enabled=False, api_key="key", session=session)
    try:
        client.synthesize({"draft_answer": "safe"})
    except GeminiSynthesisError as exc:
        assert "disponível" in str(exc)
    else:
        raise AssertionError("disabled Gemini should fail before HTTP")
    assert not session.calls


def test_gemini_parses_usage_and_configured_cost():
    client = GeminiSynthesizer(
        enabled=True,
        api_key="key",
        session=Session(),
        input_usd_per_1m=1.0,
        output_usd_per_1m=2.0,
    )
    result = client.synthesize({"route": "competency_development_rag", "draft_answer": "safe"})
    assert result.text == "Resposta final."
    assert result.input_tokens == 10
    assert result.output_tokens == 6
    assert result.total_tokens == 16
    assert result.cost == 0.000022
    assert result.cost_source == "configured_pricing"


def test_gemini_rejects_pii_before_http():
    session = Session()
    client = GeminiSynthesizer(enabled=True, api_key="key", session=session)
    try:
        client.synthesize({"draft_answer": "email pessoa@example.com"})
    except GeminiSynthesisError as exc:
        assert "PII" in str(exc)
    else:
        raise AssertionError("Gemini must reject PII")
    assert not session.calls
