import numpy as np
from src.fairness import assess_predictions


def test_fairness_reports_insufficient_groups_without_inventing_attributes():
    report = assess_predictions(
        np.array(["A", "A", "B", "B"]), np.array(["A", "B", "B", "B"])
    )
    assert report["status"].startswith("not_evaluable")
    assert report["group_metrics"] == []


def test_fairness_reports_per_track_metrics_and_gap():
    report = assess_predictions(
        np.array(["A"] * 6 + ["B"] * 6),
        np.array(["A"] * 5 + ["B"] + ["B"] * 6),
        min_support=2,
    )
    assert len(report["per_track"]) == 2
    assert report["performance_gap"] is not None
