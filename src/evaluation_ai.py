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
    from deepeval import evaluate
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
    metrics = [
        FaithfulnessMetric(model=model),
        AnswerRelevancyMetric(model=model),
        ContextualPrecisionMetric(model=model),
        ContextualRecallMetric(model=model),
    ]
    results = evaluate([test_case], metrics)
    return {
        "case_id": case.get("id"),
        "results": str(results),
        "metrics": [type(metric).__name__ for metric in metrics],
    }
