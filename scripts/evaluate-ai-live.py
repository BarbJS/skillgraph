#!/usr/bin/env python3
"""Execute current RAG backend and judge fresh outputs with DeepEval."""
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

from src.deepeval_judge import LocalDeepEvalModel  # noqa: E402
from src.evaluation_runner import run_live_evaluation  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("evals/rag_goldens.jsonl"))
    parser.add_argument("--deepeval", action="store_true")
    parser.add_argument("--deepeval-case", default="")
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--yes-live", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("output/evaluation/live_ai_report.json"))
    args = parser.parse_args()
    if not args.yes_live:
        raise SystemExit("Use --yes-live para confirmar consumo do judge.")
    if not args.deepeval:
        raise SystemExit("Use --deepeval.")
    judge = LocalDeepEvalModel(model=args.judge_model, base_url=args.base_url, api_key=args.api_key)
    report = run_live_evaluation(
        dataset_path=args.dataset,
        output_path=args.output,
        model=judge,
        case_id=args.deepeval_case,
        progress=lambda case_id, index, total: print(f"[{index}/{total}] {case_id}", flush=True),
    )
    report["judge_model"] = args.judge_model or os.getenv("EVAL_JUDGE_MODEL", "gemini-3.1-flash-lite")
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
