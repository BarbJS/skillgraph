from src.deepeval_judge import LocalDeepEvalModel


def test_judge_normalizes_openai_model_name(monkeypatch):
    monkeypatch.setenv("EVAL_JUDGE_API_KEY", "key")
    judge = LocalDeepEvalModel(model="gemini/gemini-3.1-flash-lite")
    assert judge.model_name == "gemini-3.1-flash-lite"
    assert judge.request_url().endswith("/models/gemini-3.1-flash-lite:generateContent")


def test_judge_normalizes_openai_suffix_to_native_gemini_endpoint(monkeypatch):
    monkeypatch.setenv(
        "EVAL_JUDGE_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    )
    monkeypatch.setenv("EVAL_JUDGE_API_KEY", "key")
    judge = LocalDeepEvalModel()
    assert judge.base_url == "https://generativelanguage.googleapis.com/v1beta"
    assert judge.request_url() == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"


def test_judge_normalizes_openai_segment_inside_path(monkeypatch):
    monkeypatch.setenv(
        "EVAL_JUDGE_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    monkeypatch.setenv("EVAL_JUDGE_API_KEY", "key")
    judge = LocalDeepEvalModel()
    assert judge.request_url() == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"
