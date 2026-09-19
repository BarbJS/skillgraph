from pathlib import Path

from src.answer_router import answer_competency_question, answer_structured_question
from src.intent_router import Intent
from src.sql_tools import SkillGraphDatabase


DATA_DIR = Path(__file__).parents[1] / "data_bd"


def test_structured_indicator_uses_read_only_duckdb_functions():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        result = answer_structured_question("Quais competências têm mais lacunas?", db)
        assert result.route == Intent.SQL_INDICATOR
        assert result.rows
        assert "DuckDB" in result.reason
    finally:
        db.close()


def test_structured_training_catalog_uses_read_only_duckdb_functions():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        result = answer_structured_question("Quais treinamentos estão disponíveis?", db)
        assert result.route == Intent.SQL_INDICATOR
        assert result.rows
        assert "treinamentos" in result.reason
    finally:
        db.close()


def test_competency_lookup_is_deterministic_and_non_predictive():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        result = answer_competency_question(
            "Qual é a situação da competência COMP003 para o funcionário F0001?", db
        )
        assert result.route == Intent.COMPETENCY_LOOKUP
        assert result.answer
        assert "Nível atual" in result.answer
        assert "DuckDB" in result.reason
    finally:
        db.close()
