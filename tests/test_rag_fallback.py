from pathlib import Path

from src.agents import tools


def test_local_rag_fallback_recovers_external_training_policy():
    result = tools._local_rag_fallback("Quais regras de reembolso se aplicam a um treinamento externo?")
    assert result is not None
    assert result["supported"] is True
    assert "reembolsar até 50%" in result["answer"]
    assert any(item["document"] == "faq_desenvolvimento.md" for item in result["sources"])


def test_local_rag_fallback_returns_none_for_unrelated_question():
    result = tools._local_rag_fallback("Qual é o orçamento anual do departamento de Dados?")
    assert result is None
