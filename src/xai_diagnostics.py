"""Safe diagnostics for the competency model's developer-only XAI panel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from src.ml_pipeline import load_artifact


def _metric_rows(metrics: dict[str, Any] | None) -> list[dict[str, Any]]:
    metrics = metrics or {}
    labels = {
        "macro_f1": "Macro F1",
        "balanced_accuracy": "Balanced Accuracy",
        "macro_precision": "Macro Precision",
        "macro_recall": "Macro Recall",
        "accuracy": "Accuracy",
        "top_2_accuracy": "Top-2 Accuracy",
    }
    return [
        {
            "Métrica": label,
            "Valor": (
                round(float(metrics[key]), 3) if metrics.get(key) is not None else None
            ),
        }
        for key, label in labels.items()
        if metrics.get(key) is not None
    ]


def _wrapped_importances(model: Any) -> np.ndarray | None:
    candidates = [
        model,
        getattr(model, "estimator", None),
        getattr(getattr(model, "estimator", None), "_model", None),
    ]
    for candidate in candidates:
        values = getattr(candidate, "feature_importances_", None)
        if values is not None:
            array = np.asarray(values, dtype=float)
            if array.size and np.any(array > 0):
                return array
    return None


def model_diagnostics(path: Path) -> dict[str, Any]:
    artifact = load_artifact(path)
    validation = artifact.get("validation_metrics") or {}
    test = artifact.get("test_metrics") or {}
    validation_f1 = validation.get("macro_f1")
    test_f1 = test.get("macro_f1")
    gap_alert = bool(
        validation_f1 is not None
        and test_f1 is not None
        and float(validation_f1) - float(test_f1) >= 0.20
    )
    importances = _wrapped_importances(artifact.get("model"))
    return {
        "metadata": {
            "O*NET": artifact.get("onet_version"),
            "Modelo": type(artifact.get("model")).__name__,
            "Trilhas": len(artifact.get("tracks", [])),
            "Features": len(artifact.get("feature_names", [])),
            "Seed": artifact.get("seed"),
            "Criado em": artifact.get("created_at"),
        },
        "validation": _metric_rows(validation),
        "test": _metric_rows(test),
        "generalization_alert": gap_alert,
        "generalization_message": (
            "O desempenho no teste caiu significativamente em relação à validação; interpretar a recomendação com cautela."
            if gap_alert
            else "Não foi detectado um alerta automático de queda entre validação e teste."
        ),
        "global_xai_available": importances is not None,
        "global_xai_message": (
            "Importância global disponível."
            if importances is not None
            else "Importância global não disponível: o estimador ativo não produziu contribuições positivas de features."
        ),
        "fairness_message": "Fairness entre grupos protegidos não é avaliável sem atributos autorizados; não inferir grupos a partir do O*NET.",
        "association_message": "SHAP/importâncias indicam associação preditiva do modelo, não causalidade.",
    }
