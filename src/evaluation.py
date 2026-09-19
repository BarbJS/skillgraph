"""Run deterministic Etapa 1 portions of the SkillGraph golden suite."""

from __future__ import annotations

import json
from pathlib import Path

from src.answer_router import answer_structured_question
from src.intent_router import Intent, route_question
from src.security import UserRole, evaluate_input
from src.sql_tools import SkillGraphDatabase

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = ROOT / "evals" / "golden_dataset.jsonl"
REPORT_PATH = ROOT / "output" / "evaluation" / "deterministic_report.json"


def load_cases() -> list[dict]:
    return [json.loads(line) for line in GOLDEN_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def run() -> dict:
    database = SkillGraphDatabase(ROOT / "data")
    results = []
    try:
        for case in load_cases():
            route = route_question(case["question"])
            security = evaluate_input(case["question"], UserRole.DESENVOLVEDOR)
            answer = ""
            passed = route.intent.value == case["expected_route"]
            if route.intent is Intent.BLOCKED:
                answer = security.public_message
                passed = passed and not security.allowed and case["must_block"]
            elif route.intent is Intent.SQL_INDICATOR:
                routed = answer_structured_question(case["question"], database)
                answer = routed.answer
                passed = passed and bool(routed.rows)
            results.append({"id": case["id"], "route": route.intent.value, "passed": passed, "answer_preview": answer[:240]})
    finally:
        database.close()
    report = {"total": len(results), "passed": sum(item["passed"] for item in results), "results": results}
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
