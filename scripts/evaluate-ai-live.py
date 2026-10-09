#!/usr/bin/env python3
"""Explicit live DeepEval runner; may consume local LM credits."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
from src.evaluation_ai import load_golden_cases, run_live_deepeval
from src.deepeval_judge import LocalDeepEvalModel
from src.deepeval_report import parse_evaluate_output, summarize_results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", type=Path, default=Path("evals/rag_goldens.jsonl"))
    p.add_argument("--deepeval", action="store_true")
    p.add_argument("--deepeval-case", default="")
    p.add_argument("--judge-model", default=None)
    p.add_argument("--base-url", default=None)
    p.add_argument("--api-key", default=None)
    p.add_argument("--yes-live", action="store_true")
    p.add_argument(
        "--output", type=Path, default=Path("output/evaluation/live_ai_report.json")
    )
    a = p.parse_args()
    if not a.yes_live:
        raise SystemExit(
            "Use --yes-live para confirmar consumo do LM Studio durante avaliação live."
        )
    if not a.deepeval:
        raise SystemExit("Use --deepeval.")
    cases = load_golden_cases(a.dataset)
    model = LocalDeepEvalModel(
        model=a.judge_model, base_url=a.base_url, api_key=a.api_key
    )
    selected = [
        c
        for c in cases
        if c.get("answer")
        and c.get("contexts")
        and (not a.deepeval_case or c["id"] == a.deepeval_case)
    ]
    parsed_results = []
    raw_results = []
    for case in selected:
        live = run_live_deepeval(case, model=model)
        raw_results.append(
            {"case_id": case.get("id"), "results": live.get("results", "")}
        )
        # The adapter returns the DeepEval object for compatibility; if parsing is
        # unavailable, retain a safe parse_error rather than fabricating metrics.
        parsed_results.append(
            parse_evaluate_output(case, live.get("evaluation"))
            if live.get("evaluation") is not None
            else {
                "case_id": case.get("id"),
                "category": case.get("category", ""),
                "metrics": {},
                "passed": False,
                "parse_error": "DeepEval output parser did not receive an evaluation object.",
            }
        )
    report = {
        "mode": "live",
        "cases": len(cases),
        "evaluated_cases": len(selected),
        "case_results": parsed_results,
        "raw_results": raw_results,
        "summary": summarize_results(parsed_results),
        "judge_model": a.judge_model
        or os.getenv("EVAL_JUDGE_MODEL", "meta-llama-3-8b-instruct"),
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
