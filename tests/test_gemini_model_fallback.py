from src.gemini_synthesizer import GeminiSynthesizer


class Response:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body

    def json(self):
        return self.body


class Session:
    def __init__(self):
        self.models = []

    def post(self, url, **kwargs):
        model = url.split("/models/")[1].split(":")[0]
        self.models.append(model)
        if len(self.models) == 1:
            return Response(404, {"error": {"message": "model unavailable"}})
        return Response(
            200,
            {
                "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                "usageMetadata": {
                    "promptTokenCount": 2,
                    "candidatesTokenCount": 1,
                    "totalTokenCount": 3,
                },
            },
        )


def test_gemini_does_not_fallback_on_quota(monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-fallback")
    monkeypatch.setenv("GEMINI_ALLOW_FALLBACK", "true")
    monkeypatch.setenv("GEMINI_MAX_ATTEMPTS", "2")
    session = Session()

    class QuotaSession(Session):
        def post(self, url, **kwargs):
            self.models.append(url.split("/models/")[1].split(":")[0])
            return Response(429, {"error": {"message": "quota exceeded"}})

    session = QuotaSession()
    try:
        GeminiSynthesizer(
            enabled=True, api_key="key", model="gemini-primary", session=session
        ).synthesize({"draft_answer": "safe"})
    except Exception as exc:
        assert "cota" in str(exc).casefold()
    else:
        raise AssertionError("quota must fail without fallback")
    assert session.models == ["gemini-primary"]



def test_gemini_uses_configured_fallback_model_after_404(monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-fallback")
    monkeypatch.setenv("GEMINI_ALLOW_FALLBACK", "true")
    monkeypatch.setenv("GEMINI_MAX_ATTEMPTS", "2")
    session = Session()
    result = GeminiSynthesizer(
        enabled=True, api_key="key", model="gemini-primary", session=session
    ).synthesize({"draft_answer": "safe"})
    assert result.text == "ok"
    assert session.models == ["gemini-primary", "gemini-fallback"]
