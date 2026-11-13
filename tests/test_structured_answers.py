from pathlib import Path

from src.agents.router import AgentRoute, route_turn
from src.sql_tools import SkillGraphDatabase

DATA_DIR = Path(__file__).parents[1] / "data_bd"


def test_structured_indicator_route_is_core_owned():
    assert route_turn("Quais competências têm mais lacunas?") is AgentRoute.STRUCTURED


def test_training_catalog_route_is_core_owned():
    assert route_turn("Quais treinamentos estão disponíveis?") is AgentRoute.TRAINING


def test_competency_lookup_route_is_core_owned():
    assert route_turn("Qual é a situação da competência COMP003 para o funcionário F0001?") is AgentRoute.COMPETENCY_LOOKUP


def test_database_remains_read_only_for_route_tools():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        assert db.competency_gaps()
        assert db.training_catalog()
    finally:
        db.close()
