import importlib.util
from pathlib import Path

import joblib


ROOT = Path(__file__).parents[1]
ARTIFACT = ROOT / ".ml_artifacts" / "skillgraph_competency_tracks.pkl"


def test_versioned_ml_artifact_runtime_dependencies_are_declared():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "flaml==2.7.0" in requirements
    assert "lightgbm==4.6.0" in requirements


def test_versioned_ml_artifact_loads_when_runtime_dependencies_are_available():
    assert ARTIFACT.exists()
    if importlib.util.find_spec("flaml") is None:
        return
    artifact = joblib.load(ARTIFACT)
    assert artifact["model"].__class__.__module__ == "src.ml_pipeline"
    assert artifact["model"].estimator.__class__.__module__.startswith("flaml.")
    assert artifact["model"].estimator._model.__class__.__module__.startswith("lightgbm")
