"""Model-level explanations for the SkillGraph competency recommender."""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    import shap
except Exception:  # pragma: no cover - optional explanation dependency
    shap = None


def _positive_class_index(model: Any, track: str) -> int:
    classes = list(getattr(model, "classes_", []))
    try:
        return classes.index(track)
    except ValueError:
        return 0


def local_tree_explanation(model: Any, matrix: np.ndarray, feature_names: list[str], track: str, top_k: int = 8) -> list[dict[str, Any]]:
    """Return local feature contributions for tree models, with safe fallback."""

    if shap is None or not hasattr(model, "estimator"):
        return []
    estimator = model.estimator
    try:
        explainer = shap.TreeExplainer(estimator)
        values = explainer.shap_values(matrix)
        if isinstance(values, list):
            index = _positive_class_index(model, track)
            values = values[min(index, len(values) - 1)]
        values = np.asarray(values)
        if values.ndim == 3:
            values = values[0, :, _positive_class_index(model, track)]
        else:
            values = values.reshape(-1, len(feature_names))[0]
        order = np.argsort(np.abs(values))[::-1][:top_k]
        return [
            {
                "feature": feature_names[index],
                "impact": float(values[index]),
                "direction": "positive" if values[index] >= 0 else "negative",
            }
            for index in order
            if float(values[index]) != 0
        ]
    except Exception:
        return []


def global_tree_importance(model: Any, feature_names: list[str], top_k: int = 15) -> list[dict[str, Any]]:
    """Return global tree importances for the developer-only panel."""

    estimator = getattr(model, "estimator", model)
    importances = getattr(estimator, "feature_importances_", None)
    if importances is None:
        return []
    order = np.argsort(np.asarray(importances))[::-1][:top_k]
    return [{"feature": feature_names[index], "importance": float(importances[index])} for index in order if float(importances[index]) > 0]
