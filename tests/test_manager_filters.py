from pathlib import Path

from src.sql_tools import SkillGraphDatabase


DATA_DIR = Path(__file__).parents[1] / "data_bd"


def test_manager_filter_options_are_catalog_values():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        options = db.manager_filter_options()
    finally:
        db.close()
    assert "Tecnica" in options["categorias"]
    assert "Python" in options["competencias"]
    assert "Online" in options["modalidades"]


def test_gap_filter_limits_competency_results_without_ids():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        rows = db.competency_gap_breakdown(competency="Python")
    finally:
        db.close()
    assert rows
    assert all(row["competencia"] == "Python" for row in rows)
    assert all("funcionario_id" not in row for row in rows)


def test_training_filters_limit_summary_and_kpis():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        rows = db.training_summary_filtered(modality="Online", category="Tecnica")
        kpis = db.training_kpis_filtered(modality="Online", category="Tecnica")
    finally:
        db.close()
    assert rows
    assert all(row["modalidade"] == "Online" for row in rows)
    assert kpis["registros"] >= 0
    assert 0 <= kpis["taxa_aprovacao"] <= 100
