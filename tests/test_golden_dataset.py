import json
from pathlib import Path

from src.agents.router import AgentRoute, route_turn
from src.security import UserRole, evaluate_input

ROOT = Path(__file__).parents[1]


def cases():
    path = ROOT / "evals" / "golden_dataset.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _expected(value: str) -> str:
    return {
        "rag": AgentRoute.RAG.value,
        "sql_indicator": AgentRoute.STRUCTURED.value,
    }.get(value, value)


def test_golden_dataset_has_expected_schema_and_size():
    rows = cases()
    assert len(rows) >= 15
    required = {"id", "category", "question", "expected_route", "expected_answer_facts", "must_block"}
    assert all(required.issubset(row) for row in rows)
    assert len({row["id"] for row in rows}) == len(rows)


def test_golden_routes_match_current_router_and_security():
    for row in cases():
        route = route_turn(row["question"])
        expected = _expected(row["expected_route"])
        assert route.value == expected, row["id"]
        decision = evaluate_input(row["question"], UserRole.DESENVOLVEDOR)
        assert decision.allowed is (not row["must_block"]), row["id"]


def test_golden_contains_all_current_routes():
    routes = {_expected(row["expected_route"]) for row in cases()}
    assert {
        AgentRoute.RAG.value,
        AgentRoute.STRUCTURED.value,
        AgentRoute.TRAINING.value,
        AgentRoute.ML.value,
        AgentRoute.CLARIFY.value,
        AgentRoute.COMPETENCY_LOOKUP.value,
        AgentRoute.BLOCKED.value,
    } <= routes
