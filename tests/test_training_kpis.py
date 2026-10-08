from pathlib import Path

from src.sql_tools import SkillGraphDatabase


DATA_DIR = Path(__file__).parents[1] / "data_bd"


def test_training_kpis_are_aggregate_and_non_negative():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        kpis = db.training_kpis()
    finally:
        db.close()
    assert kpis["registros"] > 0
    assert 0 <= kpis["taxa_aprovacao"] <= 100
    assert kpis["nota_media"] > 0
    assert kpis["horas_associadas"] > 0
    assert kpis["custo_catalogo_associado"] > 0
    assert kpis["reprovacoes"] >= 0
    assert all("funcionario_id" not in key for key in kpis)
