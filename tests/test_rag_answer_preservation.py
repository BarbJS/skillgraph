from src.agents.runtime import _preserve_rag_answer


def test_supported_rag_answer_is_not_replaced_by_absence_claim():
    canonical = "Os critérios incluem estar ativo há 3 meses, avaliação mínima de 3,0 e aprovação do gestor."
    assert _preserve_rag_answer(canonical, "Não encontrei essa informação.", {"sources": [{"document": "politica_treinamentos.md"}]}) == canonical


def test_supported_rag_answer_preserves_critical_facts():
    canonical = "A empresa reembolsa até 50% com aprovação prévia."
    assert _preserve_rag_answer(canonical, "A empresa pode reembolsar parte do valor.", {"sources": [{}]}) == canonical


def test_clear_synthesis_can_be_used_when_facts_are_preserved():
    canonical = "A carga mínima anual é de 20 horas."
    synthesized = "Segundo a política, a carga mínima anual é de 20 horas."
    assert _preserve_rag_answer(canonical, synthesized, {"sources": [{}]}) == synthesized
