from pathlib import Path

import pytest

from src.resume_extractor import ResumeExtractionError, extract_pdf_text


def test_non_pdf_is_rejected(tmp_path):
    path = tmp_path / "resume.txt"
    path.write_text("text")
    with pytest.raises(ResumeExtractionError):
        extract_pdf_text(path)
