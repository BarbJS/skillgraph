"""Read-only DuckDB queries over synthetic SkillGraph relational data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb


class SQLToolError(RuntimeError):
    """Raised when a safe SkillGraph query cannot be executed."""


REQUIRED_TABLES = (
    "cargos",
    "competencias",
    "funcionario_competencia",
    "funcionario_treinamento",
    "treinamentos",
)


class SkillGraphDatabase:
    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir).resolve()
        if not self.data_dir.is_dir():
            raise SQLToolError(f"Diretório de dados não encontrado: {self.data_dir}")
        self.connection = duckdb.connect(database=":memory:")
        self._load_tables()

    def _load_tables(self) -> None:
        for table in REQUIRED_TABLES:
            path = self.data_dir / f"{table}.csv"
            if not path.is_file():
                raise SQLToolError(f"CSV obrigatório não encontrado: {path.name}")
            escaped = str(path).replace("'", "''")
            self.connection.execute(
                f"CREATE TABLE {table} AS "
                f"SELECT * FROM read_csv_auto('{escaped}', header=true, sample_size=-1)"
            )

    def query(self, sql: str, *, max_rows: int = 100) -> list[dict[str, Any]]:
        normalized = sql.strip().rstrip(";").strip()
        if not normalized or not normalized.lower().startswith(("select ", "with ")):
            raise SQLToolError("Somente consultas SELECT ou WITH são permitidas.")
        forbidden = (
            "insert ",
            "update ",
            "delete ",
            "drop ",
            "alter ",
            "create ",
            "copy ",
            "attach ",
        )
        if any(token in normalized.lower() for token in forbidden):
            raise SQLToolError("A consulta contém uma operação não permitida.")
        if not 1 <= max_rows <= 1000:
            raise SQLToolError("max_rows deve estar entre 1 e 1000.")
        try:
            cursor = self.connection.execute(normalized)
            columns = [item[0] for item in cursor.description or []]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchmany(max_rows)]
        except Exception as exc:
            raise SQLToolError("Não foi possível executar a consulta SQL.") from exc

    def competency_gaps(self, *, limit: int = 10) -> list[dict[str, Any]]:
        return self.query(
            """
            SELECT c.nome AS competencia,
                   COUNT(DISTINCT fc.funcionario_id) AS funcionarios_com_deficit
            FROM funcionario_competencia fc
            JOIN competencias c ON c.competencia_id = fc.competencia_id
            WHERE CAST(fc.nivel_atual AS INTEGER) < CAST(fc.nivel_obrigatorio AS INTEGER)
            GROUP BY c.nome
            ORDER BY funcionarios_com_deficit DESC, competencia
            LIMIT 10
            """,
            max_rows=limit,
        )

    def competency_case(
        self, employee_id: str, competency_id: str
    ) -> dict[str, Any] | None:
        employee = employee_id.replace("'", "''")
        competency = competency_id.replace("'", "''")
        rows = self.query(
            f"""
            SELECT fc.funcionario_id,
                   fc.competencia_id,
                   c.nome AS competencia,
                   fc.nivel_atual,
                   fc.nivel_obrigatorio,
                   fc.data_avaliacao,
                   fc.fonte_avaliacao
            FROM funcionario_competencia fc
            JOIN competencias c ON c.competencia_id = fc.competencia_id
            WHERE fc.funcionario_id = '{employee}'
              AND fc.competencia_id = '{competency}'
            LIMIT 1
            """
        )
        return rows[0] if rows else None

    def training_summary(self, *, limit: int = 20) -> list[dict[str, Any]]:
        return self.query(
            """
            SELECT modalidade,
                   COUNT(*) AS treinamentos,
                   SUM(CAST(duracao_horas AS INTEGER)) AS horas,
                   AVG(CAST(custo AS DOUBLE)) AS custo_medio
            FROM treinamentos
            GROUP BY modalidade
            ORDER BY treinamentos DESC
            LIMIT 20
            """,
            max_rows=limit,
        )

    def training_catalog(
        self, *, competency: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT t.titulo,
                   c.nome AS competencia,
                   t.duracao_horas,
                   t.modalidade,
                   t.custo,
                   t.certificacao
            FROM treinamentos t
            LEFT JOIN competencias c
              ON c.competencia_id = t.competencia_relacionada
        """
        if competency:
            escaped = competency.replace("'", "''")
            sql += f" WHERE lower(c.nome) = lower('{escaped}')"
        return self.query(
            sql + " ORDER BY t.duracao_horas LIMIT 10", max_rows=limit
        )

    def completion_summary(self) -> list[dict[str, Any]]:
        return self.query(
            """
            SELECT aprovado,
                   COUNT(*) AS registros,
                   AVG(CAST(nota AS DOUBLE)) AS nota_media
            FROM funcionario_treinamento
            GROUP BY aprovado
            ORDER BY aprovado
            """
        )

    def close(self) -> None:
        self.connection.close()


def open_skillgraph_database(data_dir: str | Path) -> SkillGraphDatabase:
    return SkillGraphDatabase(data_dir)
