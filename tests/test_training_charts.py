from pathlib import Path

from src.sql_tools import SkillGraphDatabase


DATA_DIR = Path(__file__).parents[1] / "data_bd"


def test_training_completion_breakdown_has_only_aggregate_statuses():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        rows = db.training_completion_breakdown(modality="Online", category="Tecnica")
    finally:
        db.close()
    assert rows
    assert {row["status"] for row in rows} <= {"Aprovado", "Reprovado"}
    assert all(row["registros"] >= 0 for row in rows)
    assert all("funcionario_id" not in row for row in rows)
