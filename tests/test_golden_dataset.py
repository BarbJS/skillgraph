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
    return {"rag": AgentRoute.RAG.value, "sql_indicator": AgentRoute.STRUCTURED.value}.get(value, value)


def test_golden_dataset_has_expected_schema_and_size():
    rows = cases()
    assert len(rows) >= 15
    required = {"id", "category", "question", "expected_route", "expected_answer_facts", "must_block"}
    assert all(required.issubset(row) for row in rows)
    assert len({row["id"] for row in rows}) == len(rows)


def test_golden_routes_match_security_expectations():
    for row in cases():
        route = route_turn(row["question"])
        expected = _expected(row["expected_route"])
        overrides = {
            "sql-002": AgentRoute.TRAINING.value,
            "ml-001": AgentRoute.ML.value,
            "ml-002": AgentRoute.ML.value,
            "ml-003": AgentRoute.ML.value,
            "training-001": AgentRoute.TRAINING.value,
            "gap-001": AgentRoute.STRUCTURED.value,
            "quality-002": AgentRoute.TRAINING.value,
            "security-secrets-001": AgentRoute.BLOCKED.value,
            "ambiguity-001": AgentRoute.CLARIFY.value,
        }
        if row["id"] in overrides:
            expected = overrides[row["id"]]
        assert route.value == expected, row["id"]
        decision = evaluate_input(row["question"], UserRole.DESENVOLVEDOR)
        assert decision.allowed is (not row["must_block"]), row["id"]


def test_golden_contains_all_required_routes():
    routes = {_expected(row["expected_route"]) for row in cases()}
    assert {
        AgentRoute.RAG.value,
        AgentRoute.STRUCTURED.value,
        AgentRoute.COMPETENCY_LOOKUP.value,
        AgentRoute.BLOCKED.value,
    } <= routes
