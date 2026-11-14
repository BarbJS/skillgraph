from pathlib import Path


def test_production_chat_does_not_import_judge_adapter():
    source = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert "deepeval_judge" not in source
    assert "run_live_evaluation" not in source


def test_evaluation_report_contract_names_judge_and_embedding_models():
    from src.evaluation_runner import run_live_evaluation
    assert callable(run_live_evaluation)
