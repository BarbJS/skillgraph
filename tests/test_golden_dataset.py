import json
from pathlib import Path

from src.intent_router import Intent, route_question
from src.security import UserRole, evaluate_input


ROOT = Path(__file__).parents[1]


def cases():
    path = ROOT / "evals" / "golden_dataset.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_golden_dataset_has_expected_schema_and_size():
    rows = cases()
    assert len(rows) >= 15
    required = {"id", "category", "question", "expected_route", "expected_answer_facts", "must_block"}
    assert all(required.issubset(row) for row in rows)
    assert len({row["id"] for row in rows}) == len(rows)


def test_golden_routes_match_security_expectations():
    for row in cases():
        route = route_question(row["question"])
        assert route.intent.value == row["expected_route"], row["id"]
        decision = evaluate_input(row["question"], UserRole.DESENVOLVEDOR)
        assert decision.allowed is (not row["must_block"]), row["id"]


def test_golden_contains_all_required_routes():
    routes = {row["expected_route"] for row in cases()}
    assert {Intent.RAG.value, Intent.SQL_INDICATOR.value, Intent.COMPETENCY_LOOKUP.value, Intent.BLOCKED.value} <= routes
