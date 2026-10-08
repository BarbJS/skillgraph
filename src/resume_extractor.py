"""Local PDF text extraction boundary for the future JEV/CrewAI flow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.observability import current_trace


def _observe_extraction(path: Path, fn):
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


@dataclass(frozen=True)
class ExtractedDocument:
    filename: str
    text: str
    used_ocr: bool = False


class ResumeExtractionError(RuntimeError):
    pass


def extract_pdf_text(path: Path, *, max_size_mb: int = 10) -> ExtractedDocument:
    return _observe_extraction(
        path, lambda: _extract_pdf_text(path, max_size_mb=max_size_mb)
    )


def _extract_pdf_text(path: Path, *, max_size_mb: int = 10) -> ExtractedDocument:
    if path.suffix.casefold() != ".pdf":
        raise ResumeExtractionError("Envie um arquivo PDF.")
    if path.stat().st_size > max_size_mb * 1024 * 1024:
        raise ResumeExtractionError(f"O PDF excede o limite de {max_size_mb} MB.")
    try:
        import fitz

        document = fitz.open(path)
        text = "\n".join(page.get_text() for page in document).strip()
        document.close()
    except Exception as exc:
        raise ResumeExtractionError("Não foi possível extrair texto do PDF.") from exc
    if not text:
        from src.ocr import ocr_pdf_text

        text = ocr_pdf_text(path)
        return ExtractedDocument(path.name, text, used_ocr=True)
    return ExtractedDocument(path.name, text, used_ocr=False)
