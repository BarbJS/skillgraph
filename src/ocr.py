"""OCR fallback for scanned PDFs using local Tesseract when available."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from src.resume_extractor import ResumeExtractionError


@dataclass(frozen=True)
class OcrResult:
    """Sanitized OCR output and operational metadata."""

    text: str
    pages_processed: int
    language: str


def extract_ocr_pdf(path: Path, *, max_pages: int = 10) -> OcrResult:
    """Extract text from the first configured pages of an image-based PDF.

    The PDF and rendered images remain local and are released before this
    function returns.  Tesseract language selection is explicit so a missing
    language pack fails with an actionable message instead of silently using a
    different language.
    """

    try:
        import fitz
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise ResumeExtractionError(
            "OCR indisponível: instale PyMuPDF, pytesseract e Pillow."
        ) from exc

    if os.getenv("OCR_ENABLED", "true").casefold() != "true":
        raise ResumeExtractionError("OCR está desativado na configuração.")

    try:
        configured_max_pages = int(os.getenv("OCR_MAX_PAGES", str(max_pages)))
    except ValueError as exc:
        raise ResumeExtractionError("OCR_MAX_PAGES deve ser um número inteiro positivo.") from exc
    if configured_max_pages <= 0:
        raise ResumeExtractionError("OCR_MAX_PAGES deve ser maior que zero.")

    configured_language = os.getenv("OCR_LANG", "").strip()
    command = os.getenv("TESSERACT_CMD", "").strip()
    if command:
        pytesseract.pytesseract.tesseract_cmd = command

    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:
        raise ResumeExtractionError(
            "OCR indisponível: não foi possível executar o Tesseract. "
            "Instale o Tesseract ou configure TESSERACT_CMD."
        ) from exc

    try:
        languages = set(pytesseract.get_languages(config=""))
    except Exception as exc:
        raise ResumeExtractionError(
            "OCR indisponível: não foi possível consultar os idiomas do Tesseract."
        ) from exc
    if configured_language:
        language = configured_language
    elif {"por", "eng"}.issubset(languages):
        language = "por+eng"
    else:
        language = "eng"
    requested_languages = {item for item in language.split("+") if item}
    missing_languages = sorted(requested_languages - languages)
    if missing_languages:
        available = ", ".join(sorted(languages)) or "nenhum"
        raise ResumeExtractionError(
            f"Idioma(s) OCR indisponível(is): {', '.join(missing_languages)}. "
            f"Disponíveis: {available}. Instale o pacote de idioma ou ajuste OCR_LANG."
        )

    document = None
    pages: list[str] = []
    try:
        document = fitz.open(path)
        for index, page in enumerate(document):
            if index >= configured_max_pages:
                break
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes(
                "RGB", [pixmap.width, pixmap.height], pixmap.samples
            )
            try:
                pages.append(pytesseract.image_to_string(image, lang=language))
            finally:
                image.close()
    except ResumeExtractionError:
        raise
    except Exception as exc:
        raise ResumeExtractionError(
            "Não foi possível executar OCR no PDF. Verifique o arquivo e o Tesseract."
        ) from exc
    finally:
        if document is not None:
            document.close()

    text = "\n".join(pages).strip()
    if not text:
        raise ResumeExtractionError("OCR não encontrou texto no PDF.")
    return OcrResult(text=text, pages_processed=len(pages), language=language)


def ocr_pdf_text(path: Path, *, max_pages: int = 10) -> str:
    """Backward-compatible text-only OCR boundary."""

    return extract_ocr_pdf(path, max_pages=max_pages).text
