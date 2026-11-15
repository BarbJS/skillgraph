from src.agents import tools


def test_dify_text_answer_is_preserved_without_source_metadata(monkeypatch):
    class FakeResult:
        answer = "Resposta completa retornada pelo Dify."
        sources = []
        conversation_id = "c1"
        message_id = "m1"

    monkeypatch.setattr("src.agents.tools._local_rag_fallback", lambda question: (_ for _ in ()).throw(AssertionError("fallback não deveria ser chamado")))
    class FakeClient:
        def chat(self, question):
            return FakeResult()

    result = tools.rag_tool(FakeClient(), "pergunta documental")

    assert result["answer"] == "Resposta completa retornada pelo Dify."
    assert result["supported"] is True
    assert result["source_type"] == "dify"




def test_empty_dify_answer_uses_local_fallback(monkeypatch):
    class FakeResult:
        answer = ""
        sources = []
        conversation_id = "c1"
        message_id = "m1"

    fallback = {"answer": "Resposta local", "sources": [], "supported": True, "source_type": "local_corpus_fallback"}
    monkeypatch.setattr("src.agents.tools._local_rag_fallback", lambda question: fallback)
    class FakeClient:
        def chat(self, question):
            return FakeResult()

    result = tools.rag_tool(FakeClient(), "pergunta documental")

    assert result == {**fallback, "conversation_id": "c1", "message_id": "m1"}


def test_local_rag_fallback_recovers_external_training_policy():
    result = tools._local_rag_fallback("Quais regras de reembolso se aplicam a um treinamento externo?")
    assert result is not None
    assert result["supported"] is True
    assert "reembolsar até 50%" in result["answer"]
    assert any(item["document"] == "faq_desenvolvimento.md" for item in result["sources"])


def test_local_rag_fallback_returns_none_for_unrelated_question():
    result = tools._local_rag_fallback("Qual é o orçamento anual do departamento de Dados?")
    assert result is None
