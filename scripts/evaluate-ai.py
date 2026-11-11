#!/usr/bin/env python3
"""Run offline golden validation; live DeepEval/DeepEval is explicit and costly."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation_runner import run_deterministic_evaluation  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", type=Path, default=Path("evals/golden_dataset.jsonl")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("output/evaluation/ai_quality_report.json")
    )
    args = parser.parse_args()
    report = run_deterministic_evaluation(
        dataset_path=args.dataset,
        output_path=args.output,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
