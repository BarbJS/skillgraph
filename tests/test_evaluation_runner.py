import json

from src.evaluation_runner import run_deterministic_evaluation, run_live_evaluation


def test_live_runner_uses_rag_dataset_only(tmp_path):
    assert True


def test_deterministic_runner_writes_report(tmp_path):
    dataset = tmp_path / "golden.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "id": "x",
                "category": "security",
                "question": "x",
                "expected_route": "blocked",
                "must_block": True,
            }
        )
        + "\n"
    )
    output = tmp_path / "offline.json"
    report = run_deterministic_evaluation(dataset_path=dataset, output_path=output)
    assert report["total"] == 1
    assert output.exists()


def test_live_runner_reports_progress_and_writes_report(monkeypatch, tmp_path):
    dataset = tmp_path / "rag.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "id": "rag-1",
                "category": "rag",
                "question": "q",
                "answer": "a",
                "contexts": ["c"],
                "ground_truth": "a",
            }
        )
        + "\n"
    )
    output = tmp_path / "live.json"

    class FakeModel:
        model_name = "judge-test"

    monkeypatch.setattr(
        "src.evaluation_runner.DifyClient.from_environment",
        lambda: object(),
    )
    monkeypatch.setattr(
        "src.evaluation_runner._execute_rag_case",
        lambda case, client: case,
    )
    monkeypatch.setattr(
        "src.evaluation_runner.run_live_deepeval",
        lambda case, model: {
            "evaluation": type(
                "Evaluation",
                (),
                {
                    "metrics_data": [
                        type(
                            "Metric",
                            (),
                            {
                                "name": "Faithfulness",
                                "score": 0.5,
                                "threshold": 0.5,
                                "success": True,
                                "reason": "ok",
                                "evaluation_model": "judge-test",
                                "evaluation_cost": None,
                            },
                        )()
                    ]
                },
            )()
        },
    )
    progress = []
    report = run_live_evaluation(
        dataset_path=dataset,
        output_path=output,
        model=FakeModel(),
        progress=lambda case_id, index, total: progress.append((case_id, index, total)),
    )
    assert report["evaluated_cases"] == 1
    assert progress == [("rag-1", 1, 1)]
    assert output.exists()
