"""Ephemeral Streamlit upload boundary for resume PDFs."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from src.resume_extractor import ExtractedDocument, ResumeExtractionError, extract_pdf_text


def extract_uploaded_resume(uploaded: Any) -> ExtractedDocument:
    """Extract one uploaded PDF without retaining its bytes on disk.

    Streamlit's UploadedFile is copied to a named temporary file only for the
    duration of extraction. The file is closed and removed before returning;
    callers receive text plus safe extraction metadata, never the PDF bytes.
    """

    filename = str(getattr(uploaded, "name", "curriculo.pdf") or "curriculo.pdf")
    if Path(filename).suffix.casefold() != ".pdf":
        raise ResumeExtractionError("Envie um arquivo PDF.")
    try:
        content = uploaded.getvalue()
    except Exception as exc:
        raise ResumeExtractionError("Não foi possível ler o PDF enviado.") from exc
    if not isinstance(content, (bytes, bytearray)) or not content:
        raise ResumeExtractionError("O PDF enviado está vazio.")

    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as stream:
            stream.write(content)
            stream.flush()
            temporary = Path(stream.name)
        extracted = extract_pdf_text(temporary)
        return ExtractedDocument(
            filename=filename,
            text=extracted.text,
            used_ocr=extracted.used_ocr,
            pages_processed=extracted.pages_processed,
            extraction_method=extracted.extraction_method,
            size_bytes=extracted.size_bytes,
        )
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        del content
