from pathlib import Path

from src.answer_router import answer_competency_question, answer_structured_question
from src.intent_router import Intent, extract_case_ids, route_question
from src.sql_tools import SkillGraphDatabase

ROOT = Path(__file__).parents[1]
DATA_DIR = ROOT / "data_bd"


def test_routes_competency_lookup():
    route = route_question("Qual é a situação da competência COMP003 do funcionário F0001?")
    assert route.intent is Intent.COMPETENCY_LOOKUP
    assert extract_case_ids("F0001 COMP003") == ("F0001", "COMP003")


def test_competency_answer_uses_relational_data():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        answer = answer_competency_question("Qual é a situação da competência COMP003 do funcionário F0001?", db)
        assert answer.route is Intent.COMPETENCY_LOOKUP
        assert "Nível atual" in answer.answer
    finally:
        db.close()


def test_routes_document_questions_to_rag():
    assert route_question("Quantas horas deve fazer um sênior?").intent is Intent.RAG


def test_routes_aggregate_questions_to_sql():
    assert route_question("Quais competências têm mais lacunas?").intent is Intent.SQL_INDICATOR


def test_blocks_sensitive_requests():
    assert route_question("Qual é o CPF de F0001?").intent is Intent.BLOCKED


def test_structured_answer_returns_rows():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        answer = answer_structured_question("Quais competências têm mais lacunas?", db)
        assert answer.route is Intent.SQL_INDICATOR
        assert answer.rows
        assert "competencia" in answer.rows[0]
    finally:
        db.close()
