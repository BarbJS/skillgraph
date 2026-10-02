#!/usr/bin/env python3
"""Train the SkillGraph collaborator competency-track model with FLAML."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ml_pipeline import (
    ARTIFACT_NAME,
    SEED,
    build_track_profiles,
    build_training_frame,
    choose_model,
    fetch_onet_dataset,
    fine_tune,
    fit_final_and_test,
    profile_dataset,
    report_to_json,
    save_artifact,
    split_dataset,
    train_compare,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--time-budget", type=int, default=30)
    parser.add_argument("--tuning-budget", type=int, default=45)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--cache-dir", type=Path, default=Path(".ml_artifacts/onet"))
    parser.add_argument("--artifact", type=Path, default=Path(f".ml_artifacts/{ARTIFACT_NAME}"))
    parser.add_argument("--report", type=Path, default=Path(".ml_artifacts/competency_report.json"))
    args = parser.parse_args()

    root = fetch_onet_dataset(args.cache_dir)
    frame, metadata = build_training_frame(root)
    split = split_dataset(frame, seed=args.seed)
    preprocessor, results, _ = train_compare(split, metadata["feature_names"], time_budget=args.time_budget, seed=args.seed)
    selected = choose_model(results)
    tuned_preprocessor, tuned = fine_tune(split, selected, metadata["feature_names"], time_budget=args.tuning_budget, seed=args.seed)
    final_preprocessor, final, test_metrics = fit_final_and_test(split, tuned, metadata["feature_names"], seed=args.seed)
    track_profiles = build_track_profiles(pd.concat([split.train, split.validation], ignore_index=True), metadata["feature_names"])
    save_artifact(args.artifact, final_preprocessor, final, metadata, track_profiles, seed=args.seed)
    report = {
        "problem": "classificação multiclasse de trilhas de desenvolvimento tech para colaboradores descritos por RH",
        "dataset": metadata | {"profile": profile_dataset(frame), "split_sizes": {"train": len(split.train), "validation": len(split.validation), "test": len(split.test)}},
        "seed": args.seed,
        "validation_results": [{"name": item.name, "family": item.family, "metrics": item.validation.__dict__, "config": item.config, "error": item.error} for item in results],
        "selected": selected.name,
        "tuned": {"name": tuned.name, "metrics": tuned.validation.__dict__, "config": tuned.config},
        "test": test_metrics.__dict__,
        "artifact": str(args.artifact),
    }
    report_to_json(report, args.report)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
