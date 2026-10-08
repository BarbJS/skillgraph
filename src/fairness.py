"""Fairness and bias-risk metrics without inventing protected attributes."""

from __future__ import annotations
from typing import Any
import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score


def assess_predictions(
    y_true, y_pred, *, groups=None, min_support=5, gap_threshold=0.15
) -> dict[str, Any]:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    labels = sorted(set(y_true.tolist()) | set(y_pred.tolist()))
    per_track = []
    for label in labels:
        mask = y_true == label
        support = int(mask.sum())
        per_track.append(
            {
                "track": str(label),
                "support": support,
                "recall": float(
                    recall_score(
                        y_true, y_pred, labels=[label], average="macro", zero_division=0
                    )
                ),
                "precision": float(
                    precision_score(
                        y_true, y_pred, labels=[label], average="macro", zero_division=0
                    )
                ),
                "f1": float(
                    f1_score(
                        y_true, y_pred, labels=[label], average="macro", zero_division=0
                    )
                ),
                "insufficient_support": support < min_support,
            }
        )
    recalls = [x["recall"] for x in per_track if not x["insufficient_support"]]
    gap = max(recalls) - min(recalls) if len(recalls) > 1 else None
    report = {
        "status": "not_evaluable_without_authorized_group_attributes",
        "group_metrics": [],
        "per_track": per_track,
        "performance_gap": gap,
        "gap_threshold": gap_threshold,
        "alert": gap is not None and gap > gap_threshold,
        "insufficient_support": any(x["insufficient_support"] for x in per_track),
        "note": "Fairness entre grupos protegidos não é calculável sem atributos autorizados; não usar O*NET ocupacional como proxy de colaboradores.",
    }
    return report
