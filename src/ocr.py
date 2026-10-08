"""OCR fallback for scanned PDFs using local Tesseract when available."""

from __future__ import annotations
from pathlib import Path
from src.resume_extractor import ResumeExtractionError


def ocr_pdf_text(path: Path, *, max_pages: int = 10) -> str:
    try:
        import fitz
        import pytesseract
        import os
        from PIL import Image

        if os.getenv("OCR_ENABLED", "true").casefold() != "true":
            raise ResumeExtractionError("OCR está desativado na configuração.")
        max_pages = int(os.getenv("OCR_MAX_PAGES", str(max_pages)))
        pytesseract.pytesseract.tesseract_cmd = os.getenv(
            "TESSERACT_CMD", pytesseract.pytesseract.tesseract_cmd
        )
    except ImportError as exc:
        raise ResumeExtractionError(
            "OCR indisponível: instale pytesseract, Pillow e Tesseract."
        ) from exc
    try:
        document = fitz.open(path)
        pages = []
        for index, page in enumerate(document):
            if index >= max_pages:
                break
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes(
                "RGB", [pixmap.width, pixmap.height], pixmap.samples
            )
            pages.append(pytesseract.image_to_string(image))
        document.close()
        text = "\n".join(pages).strip()
    except Exception as exc:
        raise ResumeExtractionError("Não foi possível executar OCR no PDF.") from exc
    if not text:
        raise ResumeExtractionError("OCR não encontrou texto no PDF.")
    return text
