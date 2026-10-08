from pathlib import Path

from src.xai_diagnostics import model_diagnostics


def test_model_diagnostics_exposes_metrics_and_limits():
    report = model_diagnostics(Path(".ml_artifacts/skillgraph_competency_tracks.pkl"))
    assert report["validation"]
    assert report["test"]
    assert "generalization_alert" in report
    assert report["fairness_message"].startswith("Fairness")
    assert isinstance(report["global_xai_available"], bool)
