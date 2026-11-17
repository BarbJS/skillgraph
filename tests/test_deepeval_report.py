from types import SimpleNamespace

from src.deepeval_report import parse_test_result, summarize_results


def test_parse_and_summarize_deepeval_metrics():
    result = SimpleNamespace(
        metrics_data=[
            SimpleNamespace(name="Faithfulness", score=0.9, threshold=0.5, success=True, reason="ok", evaluation_model="judge"),
            SimpleNamespace(name="Answer Relevancy", score=0.6, threshold=0.5, success=True, reason="ok", evaluation_model="judge"),
        ]
    )
    parsed = parse_test_result("case-1", "rag", result)
    summary = summarize_results([parsed])
    assert parsed["passed"] is True
    assert summary["cases"] == 1
    assert summary["metrics"]["faithfulness"]["mean"] == 0.9
    assert summary["metrics"]["answer_relevancy"]["pass_rate"] == 1.0


def test_zero_scores_are_preserved_and_none_is_excluded_from_aggregates():
    result = SimpleNamespace(
        metrics_data=[
            SimpleNamespace(name="Contextual Precision", score=0.0, threshold=0.5, success=False, reason="no context", evaluation_model="judge"),
            SimpleNamespace(name="Contextual Recall", score=None, threshold=0.5, success=False, reason="error", evaluation_model="judge"),
        ]
    )
    parsed = parse_test_result("case-zero", "rag", result)
    summary = summarize_results([parsed])
    assert parsed["metrics"]["contextual_precision"]["score"] == 0.0
    assert parsed["metrics"]["contextual_recall"]["score"] is None
    assert parsed["passed"] is False
    assert parsed["score_coverage"] == 0.25
    assert parsed["missing_score_count"] == 1
    assert summary["metrics"]["contextual_precision"]["count"] == 1
    assert summary["metrics"]["contextual_precision"]["minimum"] == 0.0
    assert "contextual_recall" not in summary["metrics"]


def test_summary_reports_weaknesses_and_recommendation():
    result = SimpleNamespace(
        metrics_data=[
            SimpleNamespace(name="Faithfulness", score=0.4, threshold=0.5, success=False, reason="weak", evaluation_model="judge")
        ]
    )
    parsed = parse_test_result("case-2", "rag", result)
    summary = summarize_results([parsed])
    assert summary["weaknesses"][0]["case_id"] == "case-2"
    assert summary["recommendations"]
