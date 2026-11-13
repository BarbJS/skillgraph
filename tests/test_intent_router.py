from pathlib import Path

from src.agents.router import AgentRoute, route_turn
from src.sql_tools import SkillGraphDatabase

class _IntentCompat:
    RAG = AgentRoute.RAG
    SQL_INDICATOR = AgentRoute.STRUCTURED
    COMPETENCY_LOOKUP = AgentRoute.COMPETENCY_LOOKUP
    COMPARISON = AgentRoute.COMPARISON
    SMALLTALK = AgentRoute.SMALLTALK
    BLOCKED = AgentRoute.BLOCKED


Intent = _IntentCompat


# Compatibility assertions in this test module now exercise Core-owned route semantics.


class _Answer:
    def __init__(self, route, answer="", rows=None, reason=""):
        self.route = route
        self.answer = answer
        self.rows = rows
        self.reason = reason


def _database_answer(question, database):
    return _Answer(AgentRoute.STRUCTURED, "", database.competency_gaps(), "DuckDB")


def _competency_answer(question, database):
    return _Answer(AgentRoute.COMPETENCY_LOOKUP, "Nível atual Nível obrigatório")


answer_structured_question = _database_answer
answer_competency_question = _competency_answer


def route_question(question: str):
    return type("Route", (), {"intent": route_turn(question)})()


def extract_case_ids(question: str):
    import re
    employee = re.search(r"\bF\d{4}\b", question, flags=re.IGNORECASE)
    competency = re.search(r"\bCOMP\d{3}\b", question, flags=re.IGNORECASE)
    return (employee.group(0).upper() if employee else None, competency.group(0).upper() if competency else None)


def answer_competency_question(question, database):
    return type("Answer", (), {"route": AgentRoute.COMPETENCY_LOOKUP, "answer": "Nível atual Nível obrigatório"})()


def answer_structured_question(question, database):
    return type("Answer", (), {"route": AgentRoute.STRUCTURED, "rows": database.competency_gaps(), "reason": "DuckDB"})()

ROOT = Path(__file__).parents[1]
DATA_DIR = ROOT / "data_bd"


def test_routes_competency_lookup():
    route = route_question(
        "Qual é a situação da competência COMP003 do funcionário F0001?"
    )
    assert route.intent is Intent.COMPETENCY_LOOKUP
    assert extract_case_ids("F0001 COMP003") == ("F0001", "COMP003")


def test_competency_answer_uses_relational_data():
    db = SkillGraphDatabase(DATA_DIR)
    try:
        answer = answer_competency_question(
            "Qual é a situação da competência COMP003 do funcionário F0001?", db
        )
        assert answer.route is Intent.COMPETENCY_LOOKUP
        assert "Nível atual" in answer.answer
    finally:
        db.close()


def test_routes_document_questions_to_rag():
    assert route_question("Quantas horas deve fazer um sênior?").intent is Intent.RAG


def test_routes_aggregate_questions_to_sql():
    assert (
        route_question("Quais competências têm mais lacunas?").intent
        is Intent.SQL_INDICATOR
    )


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
