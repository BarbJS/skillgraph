from src.quality_ui import (
    _deterministic_report_for_display,
    _deterministic_rows,
    _live_case_rows,
    _live_metric_rows,
)


def test_deterministic_report_hides_rag_metrics():
    display = _deterministic_report_for_display(
        {
            "mode": "backend_execution",
            "total": 20,
            "ragas_metrics": ["faithfulness"],
            "results": [
                {
                    "id": "x",
                    "metrics": {"faithfulness": 1.0},
                    "passed": True,
                }
            ],
        }
    )
    assert "ragas_metrics" not in display
    assert "metrics" not in display["results"][0]


def test_must_block_is_explained_as_blocking_expectation():
    rows = _deterministic_rows(
        [{"id": "s-1", "category": "security", "question": "q", "expected_route": "blocked", "must_block": True}],
        {"results": [{"id": "s-1", "passed": True, "route": "blocked", "schema_errors": []}]},
    )
    assert rows[0]["Deve bloquear?"] == "Sim"
    assert rows[0]["Resultado offline"] == "Aprovado"
    assert "Rota observada" not in rows[0]
    assert "Erro de schema" not in rows[0]


def test_live_metric_rows_expose_general_aggregates():
    rows = _live_metric_rows(
        {"metrics": {"faithfulness": {"count": 12, "mean": 0.9514, "median": 1.0, "minimum": 0.5, "maximum": 1.0, "pass_rate": 1.0}}}
    )
    assert rows[0]["Métrica"] == "Faithfulness"
    assert rows[0]["Média geral"] == 0.9514
    assert rows[0]["Casos"] == 12


def test_live_case_rows_include_four_scores():
    rows = _live_case_rows(
        {
            "case_results": [
                {
                    "case_id": "rag-1",
                    "category": "rag",
                    "passed": True,
                    "score_mean": 0.9,
                    "metrics": {
                        "faithfulness": {"score": 0.9},
                        "answer_relevancy": {"score": 0.8},
                        "contextual_precision": {"score": 1.0},
                        "contextual_recall": {"score": 0.9},
                    },
                }
            ]
        }
    )
    assert rows[0]["Faithfulness"] == 0.9
    assert rows[0]["Contextual Recall"] == 0.9
