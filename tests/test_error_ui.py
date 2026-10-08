from src.error_ui import classify_error, sanitize_detail, technical_payload


def test_error_classification_is_safe_and_actionable():
    category, message, action = classify_error(
        "Bearer sk-secret JEV TLS certificate failed"
    )
    assert category == "JEV/TLS"
    assert "análise" in message
    assert "conexão" in action
    assert "sk-secret" not in sanitize_detail("Bearer sk-secret")


def test_technical_payload_hides_detail_for_non_developer():
    payload = technical_payload(
        trace_id="t1",
        route="resume_analysis",
        elapsed_seconds=3.2,
        error="internal secret",
        developer=False,
    )
    assert payload["Trace ID"] == "t1"
    assert "Detalhe sanitizado" not in payload


def test_technical_payload_has_sanitized_detail_for_developer():
    payload = technical_payload(
        trace_id="t1",
        route="resume_analysis",
        elapsed_seconds=3.2,
        error="Bearer sk-secret",
        developer=True,
    )
    assert payload["Detalhe sanitizado"] == "[REDACTED]"
