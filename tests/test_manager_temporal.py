from pathlib import Path

from src.sql_tools import SkillGraphDatabase


DATA_DIR = Path(__file__).parents[1] / "data_bd"


def test_training_temporal_summary_is_monthly_and_aggregate():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        rows = db.training_temporal_summary(modality="Online", category="Tecnica")
    finally:
        db.close()
    assert rows
    assert all(len(row["mes"]) == 7 for row in rows)
    assert all(row["registros"] >= 0 for row in rows)
    assert all("funcionario_id" not in row for row in rows)


def test_gap_temporal_summary_respects_competency_filter():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        rows = db.competency_gap_temporal_summary(competency="Python")
    finally:
        db.close()
    assert rows
    assert all(len(row["mes"]) == 7 for row in rows)
    assert all(row["lacunas_criticas"] >= 0 for row in rows)
    assert all("funcionario_id" not in row for row in rows)
