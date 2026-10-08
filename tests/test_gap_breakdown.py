from pathlib import Path

from src.sql_tools import SkillGraphDatabase


DATA_DIR = Path(__file__).parents[1] / "data_bd"


def test_gap_breakdown_separates_critical_and_common_gaps():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        rows = db.competency_gap_breakdown(limit=20)
    finally:
        db.close()
    assert rows
    assert {
        "competencia",
        "funcionarios_com_deficit",
        "lacunas_criticas",
        "lacunas_comuns",
        "percentual_critico",
    } <= rows[0].keys()
    assert any(row["lacunas_criticas"] > 0 for row in rows)
    assert all(row["lacunas_comuns"] >= 0 for row in rows)
    assert all("funcionario_id" not in row for row in rows)
    assert all(0 <= float(row["percentual_critico"]) <= 100 for row in rows)
