"""Structured DeepEval result parsing and summary helpers."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean, median
from typing import Any

METRICS = (
    "Faithfulness",
    "Answer Relevancy",
    "Contextual Precision",
    "Contextual Recall",
)


def _metric_name(name: str) -> str:
    return name.lower().replace(" ", "_")


def parse_test_result(case_id: str, category: str, result: Any) -> dict[str, Any]:
    metrics: dict[str, dict[str, Any]] = {}
    for item in getattr(result, "metrics_data", []) or []:
        name = str(getattr(item, "name", ""))
        if name not in METRICS:
            continue
        metrics[_metric_name(name)] = {
            "score": (
                float(getattr(item, "score"))
                if getattr(item, "score", None) is not None
                else None
            ),
            "threshold": float(getattr(item, "threshold", 0.5)),
            "success": bool(getattr(item, "success", False)),
            "reason": str(getattr(item, "reason", "") or "")[:600],
            "evaluation_model": getattr(item, "evaluation_model", None),
            "cost": getattr(item, "evaluation_cost", None),
        }
    scores = [item["score"] for item in metrics.values() if item["score"] is not None]
    return {
        "case_id": case_id,
        "category": category,
        "metrics": metrics,
        "passed": bool(metrics) and all(item["success"] for item in metrics.values()),
        "score_mean": round(mean(scores), 4) if scores else None,
    }


def parse_evaluate_output(case: dict[str, Any], evaluate_output: Any) -> dict[str, Any]:
    """Parse DeepEval evaluate() output without serializing the object repr."""
    results = getattr(evaluate_output, "test_results", None) or []
    if not results:
        return parse_test_result(
            case.get("id", ""), case.get("category", ""), evaluate_output
        )
    return parse_test_result(case.get("id", ""), case.get("category", ""), results[0])


def summarize_results(
    results: list[dict[str, Any]], *, threshold: float = 0.70
) -> dict[str, Any]:
    by_metric: dict[str, list[float]] = defaultdict(list)
    passed_by_metric: dict[str, list[bool]] = defaultdict(list)
    weaknesses: list[dict[str, Any]] = []
    by_category: dict[str, list[bool]] = defaultdict(list)
    for result in results:
        by_category[result.get("category", "unknown")].append(
            bool(result.get("passed"))
        )
        for name, metric in result.get("metrics", {}).items():
            if metric.get("score") is not None:
                by_metric[name].append(float(metric["score"]))
                passed_by_metric[name].append(bool(metric.get("success")))
                if float(metric["score"]) < threshold or not metric.get("success"):
                    weaknesses.append(
                        {
                            "case_id": result["case_id"],
                            "metric": name,
                            "score": metric["score"],
                            "reason": metric.get("reason", ""),
                        }
                    )
    metrics_summary = {}
    for name, values in by_metric.items():
        metrics_summary[name] = {
            "count": len(values),
            "mean": round(mean(values), 4),
            "median": round(median(values), 4),
            "minimum": round(min(values), 4),
            "maximum": round(max(values), 4),
            "pass_rate": round(sum(passed_by_metric[name]) / len(values), 4),
        }
    recommendations = []
    for name, data in metrics_summary.items():
        if data["mean"] < threshold:
            recommendations.append(
                f"Revisar recuperação/prompt/contexto para melhorar {name}."
            )
    if not recommendations:
        recommendations.append(
            "Manter o conjunto de avaliação e repetir a medição após mudanças no modelo ou corpus."
        )
    return {
        "cases": len(results),
        "passed_cases": sum(bool(item.get("passed")) for item in results),
        "pass_rate": (
            round(sum(bool(item.get("passed")) for item in results) / len(results), 4)
            if results
            else 0.0
        ),
        "metrics": metrics_summary,
        "categories": {
            key: {
                "cases": len(values),
                "pass_rate": round(sum(values) / len(values), 4) if values else 0.0,
            }
            for key, values in by_category.items()
        },
        "weaknesses": weaknesses,
        "recommendations": recommendations,
    }
