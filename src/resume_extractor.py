"""Local PDF extraction boundary for the JEV/CrewAI resume flow."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.observability import current_trace


@dataclass(frozen=True)
class ExtractedDocument:
    """Resume text kept in memory with non-sensitive extraction metadata."""

    filename: str
    text: str
    used_ocr: bool = False
    pages_processed: int = 0
    extraction_method: str = "text"
    size_bytes: int = 0


class ResumeExtractionError(RuntimeError):
    pass


def _observe_extraction(path: Path, fn: Callable[[], ExtractedDocument]):
    trace = current_trace()
    if not trace:
        return fn()
    with trace.span(
        "document.extract",
        "ocr",
        task_name="pdf_text_extraction",
        metadata={"filename_extension": path.suffix.lower()},
    ):
        return fn()


def extract_pdf_text(path: Path, *, max_size_mb: int | None = None) -> ExtractedDocument:
    """Extract text with PyMuPDF, falling back to local OCR when necessary."""

    return _observe_extraction(
        path, lambda: _extract_pdf_text(path, max_size_mb=max_size_mb)
    )


def _configured_max_size_mb(value: int | None) -> int:
    if value is not None:
        return value
    raw = os.getenv("RESUME_MAX_SIZE_MB", "10")
    try:
        configured = int(raw)
    except ValueError as exc:
        raise ResumeExtractionError(
            "RESUME_MAX_SIZE_MB deve ser um número inteiro positivo."
        ) from exc
    if configured <= 0:
        raise ResumeExtractionError("RESUME_MAX_SIZE_MB deve ser maior que zero.")
    return configured


def _extract_pdf_text(path: Path, *, max_size_mb: int | None = None) -> ExtractedDocument:
    if path.suffix.casefold() != ".pdf":
        raise ResumeExtractionError("Envie um arquivo PDF.")
    if not path.exists() or not path.is_file():
        raise ResumeExtractionError("O arquivo PDF não está disponível para leitura.")

    try:
        size_bytes = path.stat().st_size
    except OSError as exc:
        raise ResumeExtractionError("Não foi possível acessar o arquivo PDF.") from exc
    limit_mb = _configured_max_size_mb(max_size_mb)
    if size_bytes > limit_mb * 1024 * 1024:
        raise ResumeExtractionError(f"O PDF excede o limite de {limit_mb} MB.")

    try:
        import fitz
    except ImportError as exc:
        raise ResumeExtractionError(
            "Extração PDF indisponível: instale PyMuPDF."
        ) from exc

    document = None
    try:
        document = fitz.open(path)
        if document.page_count == 0:
            raise ResumeExtractionError("O PDF não contém páginas.")
        text = "\n".join(page.get_text() for page in document).strip()
        page_count = document.page_count
    except ResumeExtractionError:
        raise
    except Exception as exc:
        raise ResumeExtractionError(
            "Não foi possível abrir ou extrair texto do PDF."
        ) from exc
    finally:
        if document is not None:
            document.close()

    if text:
        return ExtractedDocument(
            filename=path.name,
            text=text,
            used_ocr=False,
            pages_processed=page_count,
            extraction_method="text",
            size_bytes=size_bytes,
        )

    from src.ocr import extract_ocr_pdf

    ocr_result = extract_ocr_pdf(path)
    return ExtractedDocument(
        filename=path.name,
        text=ocr_result.text,
        used_ocr=True,
        pages_processed=ocr_result.pages_processed,
        extraction_method=f"ocr:{ocr_result.language}",
        size_bytes=size_bytes,
    )
