import json
from pathlib import Path

from src.agents.crew import route_agent_roles
from src.agents.router import AgentRoute, route_turn

ROOT = Path(__file__).parents[1]


def cases():
    path = ROOT / "evals" / "agent_goldens.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_agent_golden_schema_and_unique_ids():
    rows = cases()
    assert len(rows) >= 4
    required = {
        "id",
        "category",
        "question",
        "expected_route",
        "expected_agents",
        "expected_tools",
        "must_block",
    }
    assert all(required <= row.keys() for row in rows)
    assert len({row["id"] for row in rows}) == len(rows)


def test_agent_goldens_match_router_and_agent_roles():
    for row in cases():
        route = route_turn(row["question"])
        assert route.value == row["expected_route"], row["id"]
        assert tuple(row["expected_agents"]) == route_agent_roles(row["expected_route"]), row["id"]
        assert row["must_block"] is False


def test_agent_goldens_cover_core_domain_routes():
    routes = {row["expected_route"] for row in cases()}
    assert routes >= {
        AgentRoute.ML.value,
        AgentRoute.TRAINING.value,
        AgentRoute.RAG.value,
        AgentRoute.RESUME.value,
    }
