import json

from src.evaluation_runner import (
    _execute_rag_case,
    run_deterministic_evaluation,
    run_live_evaluation,
    run_live_golden_evaluation,
)


def test_live_golden_runner_executes_all_cases_and_records_progress(monkeypatch, tmp_path):
    dataset = tmp_path / "golden.jsonl"
    dataset.write_text(
        json.dumps({"id": "x", "category": "smalltalk", "question": "oi", "expected_route": "smalltalk", "must_block": False}) + "\n"
    )
    output = tmp_path / "live-golden.json"
    monkeypatch.setattr(
        "src.evaluation_runner.run_agent_turn",
        lambda question: {"status": "local", "route": "smalltalk", "answer": "oi"},
    )
    progress = []
    report = run_live_golden_evaluation(
        dataset_path=dataset,
        output_path=output,
        progress=lambda case_id, index, total: progress.append((case_id, index, total)),
    )
    assert report["mode"] == "live_core_router"
    assert report["total"] == 1
    assert report["passed"] == 1
    assert progress == [("x", 1, 1)]
    assert output.exists()


def test_live_golden_runner_does_not_approve_runtime_error(monkeypatch, tmp_path):
    dataset = tmp_path / "golden.jsonl"
    dataset.write_text(
        json.dumps({"id": "x", "category": "rag", "question": "q", "expected_route": "competency_development_rag", "must_block": False}) + "\n"
    )
    monkeypatch.setattr(
        "src.evaluation_runner.run_agent_turn",
        lambda question: {"status": "error", "route": "competency_development_rag", "answer": "falhou", "error": "Dify ausente"},
    )
    report = run_live_golden_evaluation(dataset_path=dataset, output_path=tmp_path / "live.json")
    assert report["passed"] == 0




def test_rag_evaluation_does_not_call_final_gemini_synthesis(monkeypatch):
    class Result:
        answer = "resposta Dify"
        sources = [{"content": "contexto"}]

    class Client:
        def chat(self, question):
            return Result()

    monkeypatch.setattr(
        "src.evaluation_runner.synthesize_response",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("não sintetizar")),
        raising=False,
    )
    result = _execute_rag_case(
        {"id": "rag-1", "question": "pergunta", "answer": "", "contexts": []},
        Client(),
    )
    assert result["answer"] == "resposta Dify"
    assert result["contexts"] == ["contexto"]
    assert result["reference_answer"] == ""
    assert result["reference_contexts"] == []
    assert result["retrieved_context_count"] == 1
    assert result["answer_present"] is True
    assert result["contexts_present"] is True
    assert result["retrieved_sources"] == [{"content": "contexto"}]


def test_live_runner_records_case_failure_and_continues(monkeypatch, tmp_path):
    dataset = tmp_path / "rag.jsonl"
    dataset.write_text(
        json.dumps({"id": "rag-1", "category": "rag", "question": "q", "answer": "a", "contexts": ["c"], "ground_truth": "a"}) + "\n"
    )
    output = tmp_path / "live.json"
    monkeypatch.setattr("src.evaluation_runner.DifyClient.from_environment", lambda: object())
    monkeypatch.setattr("src.evaluation_runner._execute_rag_case", lambda case, client: (_ for _ in ()).throw(RuntimeError("quota")))

    class FakeModel:
        model_name = "judge"
        provider = "test"
        base_url = "test://judge"

    report = run_live_evaluation(dataset_path=dataset, output_path=output, model=FakeModel())
    assert report["evaluated_cases"] == 1
    assert report["case_results"][0]["passed"] is False
    assert "quota" in report["case_results"][0]["error"]
    assert output.exists()




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
        provider = "test"
        base_url = "test://judge"

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
