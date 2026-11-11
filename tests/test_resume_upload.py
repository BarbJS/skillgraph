from pathlib import Path

import fitz
import pytest

from src.resume_extractor import ResumeExtractionError
from src.resume_upload import extract_uploaded_resume


class Uploaded:
    name = "curriculo.pdf"

    def __init__(self, value):
        self.value = value

    def getvalue(self):
        return self.value


def _pdf_bytes(text="Python"):
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    value = document.tobytes()
    document.close()
    return value


def test_uploaded_resume_returns_metadata_and_removes_temporary_file(monkeypatch):
    seen = {}

    def fake_extract(path):
        seen["path"] = Path(path)
        assert seen["path"].exists()
        return type(
            "Extracted",
            (),
            {
                "filename": seen["path"].name,
                "text": "Python",
                "used_ocr": False,
                "pages_processed": 1,
                "extraction_method": "text",
                "size_bytes": 10,
            },
        )()

    monkeypatch.setattr("src.resume_upload.extract_pdf_text", fake_extract)
    result = extract_uploaded_resume(Uploaded(_pdf_bytes()))

    assert result.text == "Python"
    assert result.used_ocr is False
    assert not seen["path"].exists()


def test_uploaded_non_pdf_is_rejected():
    upload = Uploaded(b"content")
    upload.name = "resume.docx"
    with pytest.raises(ResumeExtractionError, match="PDF"):
        extract_uploaded_resume(upload)
