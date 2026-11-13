from src.agents.router import AgentRoute, route_turn


def test_greeting_routes_without_rag():
    assert route_turn("Oi") is AgentRoute.SMALLTALK


def test_domain_question_does_not_route_smalltalk():
    assert route_turn("Qual é a carga horária de um sênior?") is AgentRoute.RAG
