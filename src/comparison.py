"""Evidence-based comparison utilities for Etapa 1.

Values are extracted from retrieved document chunks at runtime; this module
contains no hardcoded business values.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ComparisonResult:
    answer: str
    rows: list[dict[str, Any]]
    sources: tuple[str, ...]
    explanation: str


_LEVEL_ALIASES = {
    "estagio": "Estágio", "estágio": "Estágio",
    "junior": "Júnior", "júnior": "Júnior",
    "pleno": "Pleno", "senior": "Sênior", "sênior": "Sênior",
    "lideranca": "Liderança", "liderança": "Liderança",
    "especialista": "Especialista",
}


def levels_in_question(question: str) -> list[str]:
    normalized = question.lower()
    found: list[str] = []
    for alias, label in _LEVEL_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", normalized) and label not in found:
            found.append(label)
    return found


def extract_hours(chunks: list[Any], requested_levels: list[str]) -> ComparisonResult:
    """Extract level/hour pairs from retrieved chunks and calculate comparisons."""

    values: dict[str, int] = {}
    sources: set[str] = set()
    for chunk in chunks:
        content_value = getattr(chunk, "content", None)
        source_value = getattr(chunk, "source", None)
        if isinstance(chunk, dict):
            content_value = chunk.get("content", "")
            source_value = chunk.get("source") or chunk.get("document", "")
        content = str(content_value or "")
        source = str(source_value or "")
        for level in requested_levels:
            escaped = re.escape(level)
            patterns = (
                rf"\|\s*{escaped}\s*\|\s*(\d+)\s*horas",
                rf"{escaped}[^\d\n]{{0,80}}(\d+)\s*horas",
            )
            for pattern in patterns:
                match = re.search(pattern, content, flags=re.IGNORECASE)
                if match:
                    values[level] = int(match.group(1))
                    sources.add(source)
                    break

    rows = [{"nível": level, "carga mínima anual (horas)": values[level]} for level in requested_levels if level in values]
    if len(rows) < 2:
        return ComparisonResult(
            "Não encontrei evidências suficientes nos documentos para comparar os níveis solicitados.",
            rows, tuple(sorted(sources)), "Foram recuperados documentos, mas não foi possível extrair os dois valores solicitados.",
        )
    low = min(row["carga mínima anual (horas)"] for row in rows)
    high = max(row["carga mínima anual (horas)"] for row in rows)
    difference = high - low
    percentage = (difference / low * 100) if low else 0
    ordered = ", ".join(f"{row['nível']}: {row['carga mínima anual (horas)']} horas" for row in rows)
    answer = f"**Comparação**\n\n{ordered}.\n\nA diferença entre o maior e o menor valor é de **{difference} horas por ano** ({percentage:.0f}% em relação ao menor valor)."
    return ComparisonResult(answer, rows, tuple(sorted(sources)), "Valores extraídos dos trechos recuperados; a diferença foi calculada automaticamente.")
