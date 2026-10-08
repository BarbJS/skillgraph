import numpy as np
from src.ml_pipeline import map_profile_skills
from src.ml_xai import global_tree_importance


def test_unknown_skills_are_reported_not_silently_zeroed():
    mapped, recognized, unknown = map_profile_skills(
        {"Python": 4, "SQL": 3, "IA generativa": 2}, ["Programming", "Mathematics"]
    )
    assert mapped == {"Programming": 4.0}
    assert recognized[0]["input"] == "Python"
    assert {item["input"] for item in unknown} == {"SQL", "IA generativa"}


def test_global_importance_unwraps_flaml_estimator():
    class Internal:
        feature_importances_ = np.array([0.0, 0.5, 0.2])

    class Wrapper:
        estimator = Internal()

    rows = global_tree_importance(Wrapper(), ["a", "b", "c"])
    assert rows[0]["feature"] == "b"
    assert rows[0]["importance"] == 0.5
