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
