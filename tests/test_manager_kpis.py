from pathlib import Path

from src.sql_tools import SkillGraphDatabase


DATA_DIR = Path(__file__).parents[1] / "data_bd"


def test_manager_kpis_are_aggregate_and_typed():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        kpis = db.manager_kpis()
    finally:
        db.close()
    assert kpis["competencias_avaliadas"] == 20
    assert kpis["funcionarios_com_lacuna"] > 0
    assert kpis["lacunas_criticas"] > 0
    assert kpis["treinamentos_registrados"] > 0
    assert kpis["horas_catalogo"] > 0
    assert 0 <= kpis["taxa_aprovacao"] <= 100
    assert kpis["nota_media"] > 0
    assert all("funcionario_id" not in key for key in kpis)
