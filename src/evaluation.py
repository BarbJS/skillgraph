"""Run route-only checks for the unified Core Router golden suite."""

from __future__ import annotations

import json
from pathlib import Path

from src.agents.router import AgentRoute, route_turn
from src.security import UserRole, evaluate_input

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = ROOT / "evals" / "golden_dataset.jsonl"
REPORT_PATH = ROOT / "output" / "evaluation" / "deterministic_report.json"


def load_cases() -> list[dict]:
    return [
        json.loads(line)
        for line in GOLDEN_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _expected_route(value: str) -> str:
    return {
        "rag": AgentRoute.RAG.value,
        "sql_indicator": AgentRoute.STRUCTURED.value,
    }.get(value, value)


def run() -> dict:
    results = []
    for case in load_cases():
        question = str(case.get("question", ""))
        route = route_turn(question)
        security = evaluate_input(question, UserRole.DESENVOLVEDOR)
        blocked = not security.allowed or route is AgentRoute.BLOCKED
        expected_blocked = bool(case.get("must_block"))
        route_ok = route.value == _expected_route(str(case.get("expected_route", "")))
        block_ok = blocked is expected_blocked
        passed = route_ok and block_ok
        results.append(
            {
                "id": case["id"],
                "route": route.value,
                "passed": passed,
                "answer_preview": "" if blocked else "Rota selecionada pelo Core Router.",
            }
        )
    report = {
        "mode": "core_router",
        "total": len(results),
        "passed": sum(item["passed"] for item in results),
        "results": results,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
