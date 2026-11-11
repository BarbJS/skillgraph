import fitz
import pytest

from src.resume_extractor import ResumeExtractionError, extract_pdf_text


def test_ocr_module_exists():
    from src.ocr import extract_ocr_pdf, ocr_pdf_text

    assert callable(extract_ocr_pdf)
    assert callable(ocr_pdf_text)


def test_non_pdf_is_rejected(tmp_path):
    path = tmp_path / "resume.txt"
    path.write_text("text")
    with pytest.raises(ResumeExtractionError):
        extract_pdf_text(path)


def test_text_pdf_reports_native_extraction(tmp_path):
    path = tmp_path / "resume.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Python e SQL")
    document.save(path)
    document.close()

    extracted = extract_pdf_text(path)

    assert extracted.text == "Python e SQL"
    assert extracted.used_ocr is False
    assert extracted.pages_processed == 1
    assert extracted.extraction_method == "text"


def test_empty_pdf_uses_ocr_and_reports_metadata(tmp_path, monkeypatch):
    path = tmp_path / "scan.pdf"
    document = fitz.open()
    document.new_page()
    document.save(path)
    document.close()

    monkeypatch.setattr(
        "src.ocr.extract_ocr_pdf",
        lambda path: type("Ocr", (), {"text": "Python", "pages_processed": 1, "language": "eng"})(),
    )
    extracted = extract_pdf_text(path)

    assert extracted.text == "Python"
    assert extracted.used_ocr is True
    assert extracted.extraction_method == "ocr:eng"


def test_ocr_disabled_is_reported(tmp_path, monkeypatch):
    path = tmp_path / "scan.pdf"
    document = fitz.open()
    document.new_page()
    document.save(path)
    document.close()
    monkeypatch.setenv("OCR_ENABLED", "false")

    with pytest.raises(ResumeExtractionError, match="desativado"):
        extract_pdf_text(path)


def test_size_limit_is_enforced(tmp_path):
    path = tmp_path / "resume.pdf"
    path.write_bytes(b"%PDF-1.4\n" + b"x" * 20)

    with pytest.raises(ResumeExtractionError, match="limite"):
        extract_pdf_text(path, max_size_mb=0)
