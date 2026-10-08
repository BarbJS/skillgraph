from src.privacy_ui import upload_privacy_notice


def test_upload_privacy_notice_is_actionable():
    notice = upload_privacy_notice().lower()
    assert "cpf" in notice
    assert "pdf" in notice
    assert "temporariamente" in notice
    assert "5 minutos" in notice
