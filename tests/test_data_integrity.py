import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data_bd"


def _rows(filename: str) -> list[dict[str, str]]:
    with (DATA_DIR / filename).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_data_files_have_expected_headers_and_rows():
    expected = {
        "cargos.csv": (
            "cargo_id",
            "titulo",
            "departamento",
            "nivel",
            "competencias_obrigatorias",
            "competencias_desejaveis",
            "salario_minimo",
            "salario_maximo",
        ),
        "competencias.csv": (
            "competencia_id",
            "nome",
            "categoria",
            "nivel_obrigatorio_minimo",
            "obsoleto_em_anos",
        ),
        "funcionario_competencia.csv": (
            "funcionario_id",
            "competencia_id",
            "nivel_atual",
            "nivel_obrigatorio",
            "data_avaliacao",
            "fonte_avaliacao",
            "risco_lacuna_critica",
        ),
        "funcionario_treinamento.csv": (
            "funcionario_id",
            "treinamento_id",
            "data_conclusao",
            "nota",
            "aprovado",
        ),
        "treinamentos.csv": (
            "treinamento_id",
            "titulo",
            "categoria",
            "competencia_relacionada",
            "duracao_horas",
            "modalidade",
            "custo",
            "certificacao",
            "pre_requisito",
        ),
    }
    for filename, headers in expected.items():
        with (DATA_DIR / filename).open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            assert tuple(next(reader)) == headers
            assert next(reader)


def test_data_primary_keys_and_references_are_valid():
    cargos = _rows("cargos.csv")
    competencias = _rows("competencias.csv")
    funcionarios_competencia = _rows("funcionario_competencia.csv")
    funcionarios_treinamento = _rows("funcionario_treinamento.csv")
    treinamentos = _rows("treinamentos.csv")

    assert len({row["cargo_id"] for row in cargos}) == len(cargos)
    competency_ids = {row["competencia_id"] for row in competencias}
    training_ids = {row["treinamento_id"] for row in treinamentos}
    assert len(competency_ids) == len(competencias)
    assert len(training_ids) == len(treinamentos)
    assert {row["competencia_id"] for row in funcionarios_competencia} <= competency_ids
    assert {row["treinamento_id"] for row in funcionarios_treinamento} <= training_ids
    assert {row["competencia_relacionada"] for row in treinamentos} <= competency_ids
