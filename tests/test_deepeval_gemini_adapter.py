import json

from src.deepeval_embeddings import GeminiEvaluationEmbeddings
from src.deepeval_judge import LocalDeepEvalModel


class Response:
    def __init__(self, payload):
        self.payload = payload
    def raise_for_status(self):
        pass
    def json(self):
        return self.payload


class Session:
    def __init__(self):
        self.calls = []
    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "embedContent" in url:
            return Response({"embedding": {"values": [0.1, 0.2]}})
        return Response({
            "candidates": [{"content": {"parts": [{"text": "judge output"}]}}],
            "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2},
        })


def test_judge_uses_google_gemini_endpoint(monkeypatch):
    session = Session()
    monkeypatch.setenv("EVAL_JUDGE_API_KEY", "judge-key")
    judge = LocalDeepEvalModel(session=session)
    assert judge.generate("evaluate") == "judge output"
    assert session.calls[0][0].endswith("/models/gemini-3.1-flash-lite:generateContent")
    assert judge.last_usage["promptTokenCount"] == 3


def test_embeddings_use_configured_gemini_embedding_model(monkeypatch):
    session = Session()
    monkeypatch.setenv("EVAL_EMBEDDING_API_KEY", "embedding-key")
    embeddings = GeminiEvaluationEmbeddings(session=session)
    assert embeddings.embed_text("document") == [0.1, 0.2]
    assert session.calls[0][0].endswith("/models/gemini-embedding-001:embedContent")
