"""Offline-first AI quality evaluation with Golden Dataset and DeepEval."""

from __future__ import annotations
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class QualityScores:
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    deepeval_passed: bool | None = None
    judge_reason: str = ""

    def as_dict(self):
        return asdict(self)


def load_golden_cases(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def validate_golden_case(case: dict[str, Any]) -> list[str]:
    return sorted(
        {"id", "category", "question", "expected_route", "must_block"} - set(case)
    )


def evaluate_offline(
    case: dict[str, Any],
    *,
    actual_route: str | None = None,
    blocked: bool | None = None,
) -> dict[str, Any]:
    errors = validate_golden_case(case)
    route_ok = actual_route is None or actual_route == case["expected_route"]
    block_ok = blocked is None or blocked is bool(case["must_block"])
    return {
        "id": case.get("id", ""),
        "route_ok": route_ok,
        "block_ok": block_ok,
        "schema_errors": errors,
        "passed": not errors and route_ok and block_ok,
    }


def run_live_deepeval(case: dict[str, Any], *, model: Any) -> dict[str, Any]:
    """Evaluate one case sequentially to avoid provider quota bursts.

    DeepEval's default async/concurrent execution can issue the four judge
    requests at once. That is especially likely to trigger a Gemini RPM/TPM
    limit in Streamlit Cloud even when the daily quota is still available.
    Running one metric at a time also preserves partial scores and the exact
    provider error for the metric that failed.
    """
    from types import SimpleNamespace

    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
    )
    from deepeval.test_case import LLMTestCase

    test_case = LLMTestCase(
        input=case["question"],
        actual_output=case.get("answer", ""),
        expected_output=case.get("ground_truth", ""),
        retrieval_context=case.get("contexts", []),
    )
    metric_types = (
        ("Faithfulness", FaithfulnessMetric),
        ("Answer Relevancy", AnswerRelevancyMetric),
        ("Contextual Precision", ContextualPrecisionMetric),
        ("Contextual Recall", ContextualRecallMetric),
    )
    metric_results = []
    for metric_name, metric_type in metric_types:
        metric = metric_type(model=model, async_mode=False, include_reason=True)
        try:
            metric.measure(test_case, _show_indicator=False)
        except Exception as exc:
            metric.score = None
            metric.success = False
            metric.reason = f"{type(exc).__name__}: {exc}"[:600]
        metric_results.append(
            SimpleNamespace(
                name=metric_name,
                score=getattr(metric, "score", None),
                threshold=getattr(metric, "threshold", 0.5),
                success=bool(getattr(metric, "success", False)),
                reason=str(getattr(metric, "reason", "") or "")[:600],
                evaluation_model=getattr(metric, "evaluation_model", None),
                evaluation_cost=getattr(metric, "evaluation_cost", None),
            )
        )
    evaluation = SimpleNamespace(metrics_data=metric_results)
    return {
        "case_id": case.get("id"),
        "results": "sequential",
        "evaluation": evaluation,
        "metrics": [metric_type.__name__ for _, metric_type in metric_types],
    }


def run_live_deepeval_legacy(case: dict[str, Any], *, model: Any) -> dict[str, Any]:
    """Compatibility helper for callers that need DeepEval's aggregate runner."""
    from deepeval import evaluate
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
    )
    from deepeval.test_case import LLMTestCase
    from deepeval.evaluate.configs import AsyncConfig, DisplayConfig

    test_case = LLMTestCase(
        input=case["question"],
        actual_output=case.get("answer", ""),
        expected_output=case.get("ground_truth", ""),
        retrieval_context=case.get("contexts", []),
    )
    metrics = [
        FaithfulnessMetric(model=model, async_mode=False),
        AnswerRelevancyMetric(model=model, async_mode=False),
        ContextualPrecisionMetric(model=model, async_mode=False),
        ContextualRecallMetric(model=model, async_mode=False),
    ]
    results = evaluate(
        [test_case],
        metrics,
        async_config=AsyncConfig(run_async=False),
        display_config=DisplayConfig(show_indicator=False),
    )
    return {
        "case_id": case.get("id"),
        "results": str(results),
        "evaluation": results,
        "metrics": [type(metric).__name__ for metric in metrics],
    }
