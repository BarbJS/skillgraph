from src.answer_router import answer_smalltalk_question
from src.intent_router import Intent, route_question


def test_greeting_routes_without_rag():
    assert route_question("Oi").intent is Intent.SMALLTALK
    result = answer_smalltalk_question("Oi")
    assert "Olá" in result.answer


def test_domain_question_does_not_route_smalltalk():
    assert route_question("Qual é a carga horária de um sênior?").intent is Intent.RAG
