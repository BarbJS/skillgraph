from src.agents.router import AgentRoute, route_turn


def test_training_eligibility_question_uses_documentary_rag():
    assert route_turn(
        "Quais são os critérios básicos para um colaborador participar de um treinamento?"
    ) is AgentRoute.RAG


def test_training_catalog_question_stays_catalog_route():
    assert route_turn("Quais treinamentos estão disponíveis?") is AgentRoute.TRAINING


def test_training_policy_variants_use_rag():
    assert route_turn("Qual avaliação mínima é necessária para participar?") is AgentRoute.RAG
    assert route_turn("É preciso aprovação do gestor para fazer o curso?") is AgentRoute.RAG
