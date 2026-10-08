from pathlib import Path

from src.skill_graph_ui import build_graph_data, graph_enabled

ROOT = Path(__file__).parents[1]


def test_graph_data_contains_catalog_nodes_and_deduplicated_edges():
    data = build_graph_data(ROOT / "data_bd")
    assert len(data["nodes"]) == 20
    assert data["edges"]
    pairs = {(edge["source"], edge["target"]) for edge in data["edges"]}
    assert len(pairs) == len(data["edges"])
    assert all(node["label"] for node in data["nodes"])


def test_graph_nodes_include_training_relationships():
    data = build_graph_data(ROOT / "data_bd")
    python = next(node for node in data["nodes"] if node["label"] == "Python")
    assert python["trainings"]
    assert python["category"] in {"Tecnica", "Técnica"}


def test_graph_can_be_rolled_back(monkeypatch):
    monkeypatch.setenv("SKILLGRAPH_GRAPH_ENABLED", "false")
    assert graph_enabled() is False


def test_graph_is_enabled_by_default_when_unset(monkeypatch):
    monkeypatch.delenv("SKILLGRAPH_GRAPH_ENABLED", raising=False)
    assert graph_enabled() is True
