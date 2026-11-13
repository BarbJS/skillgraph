from src.privacy import (
    contains_employment_decision,
    contains_protected_pii,
    redact_text,
    sanitize,
)


def test_redaction_removes_sensitive_values():
    text, found = redact_text("CPF 12345678901 email teste@example.com")
    assert "12345678901" not in text
    assert "teste@example.com" not in text
    assert found


def test_sanitize_drops_raw_resume_and_reasoning():
    value = sanitize({"resume_text": "private", "reasoning": "secret", "route": "rag"})
    assert "resume_text" not in value
    assert "reasoning" not in value
    assert value["route"] == "rag"


def test_employment_decision_is_detected():
    assert contains_employment_decision("contratar este candidato")
    assert contains_protected_pii("CPF 12345678901")


def test_decimal_model_scores_are_not_misclassified_as_phone_numbers():
    text = '{"compatibility": 0.29999999999999993, "gap": 4.9399999999999995}'
    assert not contains_protected_pii(text)
    assert sanitize(text) == text


def test_phone_numbers_are_still_protected():
    assert contains_protected_pii("telefone: +55 (11) 99999-9999")
    assert contains_protected_pii("11 99999-9999")
    assert not contains_protected_pii("compatibility: 0.2")
    assert not contains_protected_pii("coverage: 0.333")
