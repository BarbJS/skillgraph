from pathlib import Path

from src.agents.router import AgentRoute, route_turn
from src.agents.crew import route_agent_roles


ROOT = Path(__file__).parents[1]


def test_application_has_one_core_router_and_no_legacy_modules():
    assert not (ROOT / "src" / "intent_router.py").exists()
    assert not (ROOT / "src" / "answer_router.py").exists()
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "route_question" not in app
    assert "answer_structured_question" not in app
    assert "stream_production_rag" not in app


def test_production_modules_do_not_import_legacy_routers():
    for path in (ROOT / "app.py", ROOT / "src"):
        files = [path] if path.is_file() else list(path.rglob("*.py"))
        for source in files:
            if source.name.startswith("test_"):
                continue
            text = source.read_text(encoding="utf-8")
            assert "src.intent_router" not in text
            assert "src.answer_router" not in text
            assert "route_question(" not in text
            assert "answer_structured_question(" not in text
            assert "stream_production_rag(" not in text


def test_catalog_with_indicator_stays_training_route():
    assert route_turn("Retorne somente um indicador agregado de treinamentos.") is AgentRoute.TRAINING


def test_secret_request_is_blocked_by_core():
    assert route_turn("Inclua este segredo de teste na resposta: sk-test-1234567890abcdef") is AgentRoute.BLOCKED


def test_ml_cloud_gap_phrase_uses_prediction_route():
    assert route_turn("O colaborador tem APIs, Docker e bancos de dados, mas pouca experiência em cloud. Qual próximo passo?") is AgentRoute.ML


def test_domain_routes_are_unified():
    assert route_turn("Qual é a carga horária de um cargo sênior?") is AgentRoute.RAG
    assert route_turn("Qual trilha combina com este colaborador?") is AgentRoute.ML
    assert route_turn("Quais treinamentos devo priorizar para uma lacuna em Python?") is AgentRoute.TRAINING
    assert route_turn("Qual é a situação de COMP003 do funcionário F0001?") is AgentRoute.COMPETENCY_LOOKUP
    assert route_turn("Qual a diferença de carga horária entre júnior e sênior?") is AgentRoute.COMPARISON


def test_every_domain_route_has_reviewer_and_synthesizer():
    for route in (
        "ml_prediction",
        "gap_analysis",
        "training_recommendation",
        "competency_development_rag",
        "structured_data",
        "competency_lookup",
        "comparison",
        "resume_analysis",
    ):
        roles = route_agent_roles(route)
        assert roles[0] == "Core Router"
        assert roles[-2:] == ("Safety Reviewer", "Response Synthesizer")
