"""Read-only DuckDB queries over synthetic SkillGraph relational data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from src.observability import TraceContext


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

    def query(
        self,
        sql: str,
        *,
        max_rows: int = 100,
        trace: TraceContext | None = None,
        operation: str = "duckdb.query",
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:

        span = trace.span(operation, "duckdb", task_name=operation) if trace else None
        if span:
            span.__enter__()
        try:
            return self._query_impl(sql, max_rows=max_rows, params=params)
        except Exception as exc:
            if span:
                span.__exit__(type(exc), exc, exc.__traceback__)
            raise
        finally:
            if span and span.record is None:
                span.__exit__(None, None, None)

    def _query_impl(
        self, sql: str, *, max_rows: int = 100, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:

        normalized = sql.strip().rstrip(";").strip()
        if not normalized or not normalized.lower().startswith(("select", "with")):
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
            cursor = self.connection.execute(normalized, params)
            columns = [item[0] for item in cursor.description or []]
            return [
                dict(zip(columns, row, strict=True))
                for row in cursor.fetchmany(max_rows)
            ]
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

    def manager_filter_options(self) -> dict[str, list[str]]:
        """Return safe catalog values for manager filters."""
        categories = self.query(
            "SELECT DISTINCT categoria FROM competencias ORDER BY categoria"
        )
        competencies = self.query(
            "SELECT DISTINCT nome FROM competencias ORDER BY nome"
        )
        modalities = self.query(
            "SELECT DISTINCT modalidade FROM treinamentos ORDER BY modalidade"
        )
        return {
            "categorias": [
                str(row["categoria"]) for row in categories if row.get("categoria")
            ],
            "competencias": [
                str(row["nome"]) for row in competencies if row.get("nome")
            ],
            "modalidades": [
                str(row["modalidade"]) for row in modalities if row.get("modalidade")
            ],
        }

    def competency_gap_breakdown(
        self,
        *,
        limit: int = 10,
        category: str | None = None,
        competency: str | None = None,
    ) -> list[dict[str, Any]]:
        """Separate ordinary and explicitly critical aggregate gaps."""
        return self.query(
            """SELECT
                c.nome AS competencia,
                COUNT(DISTINCT fc.funcionario_id) AS funcionarios_com_deficit,
                COUNT(*) FILTER (WHERE CAST(fc.risco_lacuna_critica AS INTEGER) = 1) AS lacunas_criticas,
                COUNT(*) FILTER (WHERE CAST(fc.risco_lacuna_critica AS INTEGER) <> 1) AS lacunas_comuns,
                ROUND(100.0 * COUNT(*) FILTER (WHERE CAST(fc.risco_lacuna_critica AS INTEGER) = 1) / NULLIF(COUNT(*), 0), 1) AS percentual_critico
            FROM funcionario_competencia fc
            JOIN competencias c ON c.competencia_id = fc.competencia_id
            WHERE CAST(fc.nivel_atual AS INTEGER) < CAST(fc.nivel_obrigatorio AS INTEGER)
              AND (? IS NULL OR c.categoria = ?)
              AND (? IS NULL OR c.nome = ?)
            GROUP BY c.nome
            ORDER BY lacunas_criticas DESC, funcionarios_com_deficit DESC, competencia
            LIMIT 10""",
            max_rows=limit,
            params=(category, category, competency, competency),
        )

    def training_kpis(self) -> dict[str, int | float]:
        """Return aggregate, non-identifying training indicators."""
        row = self.connection.execute(
            """SELECT
                COUNT(*) AS registros,
                COALESCE(AVG(CASE WHEN lower(CAST(ft.aprovado AS VARCHAR)) IN ('true', '1') THEN 1.0 ELSE 0.0 END), 0) AS taxa_aprovacao,
                COALESCE(AVG(CAST(ft.nota AS DOUBLE)), 0) AS nota_media,
                COALESCE(SUM(CAST(t.duracao_horas AS INTEGER)), 0) AS horas_associadas,
                COALESCE(SUM(CAST(t.custo AS DOUBLE)), 0) AS custo_catalogo_associado,
                COUNT(*) FILTER (WHERE lower(CAST(ft.aprovado AS VARCHAR)) NOT IN ('true', '1')) AS reprovacoes
            FROM funcionario_treinamento ft
            LEFT JOIN treinamentos t ON t.treinamento_id = ft.treinamento_id"""
        ).fetchone()
        if row is None:
            raise SQLToolError(
                "Não foi possível calcular os indicadores de treinamentos."
            )
        return {
            "registros": int(row[0] or 0),
            "taxa_aprovacao": round(float(row[1] or 0) * 100, 1),
            "nota_media": round(float(row[2] or 0), 1),
            "horas_associadas": int(row[3] or 0),
            "custo_catalogo_associado": round(float(row[4] or 0), 2),
            "reprovacoes": int(row[5] or 0),
        }

    def training_completion_breakdown(
        self, *, modality: str | None = None, category: str | None = None
    ) -> list[dict[str, Any]]:
        """Return approved/reproved aggregate counts and average notes."""
        return self.query(
            """SELECT CASE WHEN lower(CAST(ft.aprovado AS VARCHAR)) IN ('true','1') THEN 'Aprovado' ELSE 'Reprovado' END AS status,
                COUNT(*) AS registros, AVG(CAST(ft.nota AS DOUBLE)) AS nota_media
            FROM funcionario_treinamento ft LEFT JOIN treinamentos t ON t.treinamento_id = ft.treinamento_id
            WHERE (? IS NULL OR t.modalidade = ?) AND (? IS NULL OR t.categoria = ?)
            GROUP BY status ORDER BY status""",
            max_rows=10,
            params=(modality, modality, category, category),
        )

    def training_temporal_summary(
        self, *, modality: str | None = None, category: str | None = None
    ) -> list[dict[str, Any]]:
        """Aggregate training records by completion month without identifiers."""
        return self.query(
            """SELECT strftime(CAST(ft.data_conclusao AS DATE), '%Y-%m') AS mes,
                COUNT(*) AS registros,
                COUNT(*) FILTER (WHERE lower(CAST(ft.aprovado AS VARCHAR)) IN ('true','1')) AS aprovados,
                COUNT(*) FILTER (WHERE lower(CAST(ft.aprovado AS VARCHAR)) NOT IN ('true','1')) AS reprovados,
                ROUND(AVG(CAST(ft.nota AS DOUBLE)), 1) AS nota_media,
                COALESCE(SUM(CAST(t.duracao_horas AS INTEGER)), 0) AS horas
            FROM funcionario_treinamento ft LEFT JOIN treinamentos t ON t.treinamento_id = ft.treinamento_id
            WHERE (? IS NULL OR t.modalidade = ?) AND (? IS NULL OR t.categoria = ?)
            GROUP BY mes ORDER BY mes""",
            max_rows=1000,
            params=(modality, modality, category, category),
        )

    def competency_gap_temporal_summary(
        self, *, category: str | None = None, competency: str | None = None
    ) -> list[dict[str, Any]]:
        """Aggregate competency gaps by assessment month without identifiers."""
        return self.query(
            """SELECT strftime(CAST(fc.data_avaliacao AS DATE), '%Y-%m') AS mes,
                COUNT(*) AS deficits,
                COUNT(*) FILTER (WHERE CAST(fc.risco_lacuna_critica AS INTEGER) = 1) AS lacunas_criticas,
                COUNT(*) FILTER (WHERE CAST(fc.risco_lacuna_critica AS INTEGER) <> 1) AS lacunas_comuns
            FROM funcionario_competencia fc JOIN competencias c ON c.competencia_id = fc.competencia_id
            WHERE CAST(fc.nivel_atual AS INTEGER) < CAST(fc.nivel_obrigatorio AS INTEGER)
              AND (? IS NULL OR c.categoria = ?) AND (? IS NULL OR c.nome = ?)
            GROUP BY mes ORDER BY mes""",
            max_rows=1000,
            params=(category, category, competency, competency),
        )

    def training_summary_filtered(
        self,
        *,
        modality: str | None = None,
        category: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return self.query(
            """SELECT modalidade, COUNT(*) AS treinamentos,
                SUM(CAST(duracao_horas AS INTEGER)) AS horas,
                AVG(CAST(custo AS DOUBLE)) AS custo_medio
            FROM treinamentos
            WHERE (? IS NULL OR modalidade = ?) AND (? IS NULL OR categoria = ?)
            GROUP BY modalidade ORDER BY treinamentos DESC""",
            max_rows=limit,
            params=(modality, modality, category, category),
        )

    def training_kpis_filtered(
        self,
        *,
        modality: str | None = None,
        category: str | None = None,
        status: str | None = None,
    ) -> dict[str, int | float]:
        approved_clause = (
            "" if status is None else " AND lower(CAST(ft.aprovado AS VARCHAR)) = ?"
        )
        params = (status,) if status is not None else ()
        row = self.connection.execute(
            """SELECT COUNT(*), COALESCE(AVG(CASE WHEN lower(CAST(ft.aprovado AS VARCHAR)) IN ('true','1') THEN 1.0 ELSE 0.0 END),0), COALESCE(AVG(CAST(ft.nota AS DOUBLE)),0), COALESCE(SUM(CAST(t.duracao_horas AS INTEGER)),0), COUNT(*) FILTER (WHERE lower(CAST(ft.aprovado AS VARCHAR)) NOT IN ('true','1'))
            FROM funcionario_treinamento ft LEFT JOIN treinamentos t ON t.treinamento_id = ft.treinamento_id
            WHERE (? IS NULL OR t.modalidade = ?) AND (? IS NULL OR t.categoria = ?)"""
            + approved_clause,
            (modality, modality, category, category, *params),
        ).fetchone()
        return {
            "registros": int(row[0] or 0),
            "taxa_aprovacao": round(float(row[1] or 0) * 100, 1),
            "nota_media": round(float(row[2] or 0), 1),
            "horas_associadas": int(row[3] or 0),
            "reprovacoes": int(row[4] or 0),
        }

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
        return self.query(sql + " ORDER BY t.duracao_horas LIMIT 10", max_rows=limit)

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

    def manager_kpis(self) -> dict[str, int | float]:
        """Return only aggregate, non-identifying indicators for managers."""
        row = self.connection.execute(
            """
            SELECT
                (SELECT COUNT(DISTINCT competencia_id) FROM funcionario_competencia) AS competencias_avaliadas,
                (SELECT COUNT(DISTINCT funcionario_id)
                   FROM funcionario_competencia
                  WHERE CAST(nivel_atual AS INTEGER) < CAST(nivel_obrigatorio AS INTEGER)) AS funcionarios_com_lacuna,
                (SELECT COUNT(*)
                   FROM funcionario_competencia
                  WHERE CAST(risco_lacuna_critica AS INTEGER) = 1) AS lacunas_criticas,
                (SELECT COUNT(*) FROM funcionario_treinamento) AS treinamentos_registrados,
                (SELECT COALESCE(SUM(CAST(duracao_horas AS INTEGER)), 0) FROM treinamentos) AS horas_catalogo,
                (SELECT COALESCE(AVG(CAST(nota AS DOUBLE)), 0) FROM funcionario_treinamento) AS nota_media,
                (SELECT COALESCE(AVG(CASE WHEN lower(CAST(aprovado AS VARCHAR)) IN ('true', '1') THEN 1.0 ELSE 0.0 END), 0)
                   FROM funcionario_treinamento) AS taxa_aprovacao
            """
        ).fetchone()
        if row is None:
            raise SQLToolError("Não foi possível calcular os indicadores gerenciais.")
        return {
            "competencias_avaliadas": int(row[0] or 0),
            "funcionarios_com_lacuna": int(row[1] or 0),
            "lacunas_criticas": int(row[2] or 0),
            "treinamentos_registrados": int(row[3] or 0),
            "horas_catalogo": int(row[4] or 0),
            "nota_media": round(float(row[5] or 0), 1),
            "taxa_aprovacao": round(float(row[6] or 0) * 100, 1),
        }

    def close(self) -> None:
        self.connection.close()


def open_skillgraph_database(data_dir: str | Path) -> SkillGraphDatabase:
    return SkillGraphDatabase(data_dir)
