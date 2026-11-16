from src.evaluation_ai import run_live_deepeval


def test_live_deepeval_runs_each_metric_sequentially(monkeypatch):
    calls = []

    class Metric:
        def __init__(self, **kwargs):
            self.threshold = 0.5
            self.score = None
            self.success = False
            self.reason = ""
            self.evaluation_model = "fake"
            self.evaluation_cost = None

        def measure(self, test_case, _show_indicator=False):
            calls.append(type(self).__name__)
            self.score = 0.9
            self.success = True
            self.reason = "ok"
            return self.score

    class FakeFaithfulness(Metric):
        pass

    class FakeRelevancy(Metric):
        pass

    class FakePrecision(Metric):
        pass

    class FakeRecall(Metric):
        pass

    monkeypatch.setattr("deepeval.metrics.FaithfulnessMetric", FakeFaithfulness)
    monkeypatch.setattr("deepeval.metrics.AnswerRelevancyMetric", FakeRelevancy)
    monkeypatch.setattr("deepeval.metrics.ContextualPrecisionMetric", FakePrecision)
    monkeypatch.setattr("deepeval.metrics.ContextualRecallMetric", FakeRecall)

    result = run_live_deepeval(
        {
            "id": "rag-1",
            "question": "q",
            "answer": "a",
            "ground_truth": "a",
            "contexts": ["c"],
        },
        model=object(),
    )

    assert calls == [
        "FakeFaithfulness",
        "FakeRelevancy",
        "FakePrecision",
        "FakeRecall",
    ]
    assert len(result["evaluation"].metrics_data) == 4
    assert all(item.score == 0.9 for item in result["evaluation"].metrics_data)
