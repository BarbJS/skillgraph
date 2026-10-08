#!/usr/bin/env python3
"""Run offline golden validation; live DeepEval/DeepEval is explicit and costly."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation_ai import evaluate_offline, load_golden_cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", type=Path, default=Path("evals/golden_dataset.jsonl")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("output/evaluation/ai_quality_report.json")
    )
    args = parser.parse_args()
    cases = load_golden_cases(args.dataset)
    results = [evaluate_offline(case) for case in cases]
    report = {
        "mode": "offline",
        "total": len(results),
        "passed_schema": sum(not item["schema_errors"] for item in results),
        "results": results,
        "DeepEval_metrics": [
            "faithfulness",
            "answer_relevancy",
            "context_precision",
            "context_recall",
        ],
        "live_mode": "Use a separate explicit runner with configured judge credentials.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
