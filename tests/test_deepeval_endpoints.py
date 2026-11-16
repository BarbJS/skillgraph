from src.deepeval_embeddings import GeminiEvaluationEmbeddings
from src.deepeval_judge import LocalDeepEvalModel


def test_judge_normalizes_openai_suffix_to_native_gemini_endpoint(monkeypatch):
    monkeypatch.setenv(
        "EVAL_JUDGE_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    )
    monkeypatch.setenv("EVAL_JUDGE_API_KEY", "key")
    judge = LocalDeepEvalModel()
    assert judge.base_url == "https://generativelanguage.googleapis.com/v1beta"


def test_embedding_normalizes_openai_suffix_to_native_gemini_endpoint(monkeypatch):
    monkeypatch.setenv(
        "EVAL_EMBEDDING_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    )
    monkeypatch.setenv("EVAL_EMBEDDING_API_KEY", "key")
    embeddings = GeminiEvaluationEmbeddings()
    assert embeddings.base_url == "https://generativelanguage.googleapis.com/v1beta"
