from pathlib import Path

import pytest

from src.sql_tools import SQLToolError, SkillGraphDatabase


DATA_DIR = Path(__file__).parents[1] / "data_bd"


def test_database_loads_project_csvs_and_runs_join():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        rows = db.query(
            """
            SELECT c.nome, COUNT(*) AS total
            FROM funcionario_competencia fc
            JOIN competencias c ON c.competencia_id = fc.competencia_id
            GROUP BY c.nome
            ORDER BY total DESC
            LIMIT 3
            """
        )
        assert rows
        assert "nome" in rows[0]
        assert "total" in rows[0]
    finally:
        db.close()


def test_relational_indicator_query_returns_aggregates():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        rows = db.query(
            """
            SELECT competencia_id, COUNT(DISTINCT funcionario_id) AS total
            FROM funcionario_competencia
            WHERE CAST(nivel_atual AS INTEGER) < CAST(nivel_obrigatorio AS INTEGER)
            GROUP BY competencia_id
            ORDER BY total DESC
            """
        )
        assert rows
        assert "competencia_id" in rows[0]
        assert "total" in rows[0]
    finally:
        db.close()



def test_write_queries_are_rejected():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        with pytest.raises(SQLToolError):
            db.query("DELETE FROM competencias")
    finally:
        db.close()
