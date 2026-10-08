import pytest

from src.resume_extractor import ResumeExtractionError, extract_pdf_text


def test_ocr_module_exists():
    from src.ocr import ocr_pdf_text

    assert callable(ocr_pdf_text)


def test_non_pdf_is_rejected(tmp_path):
    path = tmp_path / "resume.txt"
    path.write_text("text")
    with pytest.raises(ResumeExtractionError):
        extract_pdf_text(path)
