from src.agents.runtime import _ml_deterministic_draft
from src.ml_inference import normalize_skill_name


def test_ml_aliases_cover_api_docker_and_database_terms():
    assert normalize_skill_name("APIs") == "Technology Design"
    assert normalize_skill_name("Docker") == "Technology Design"
    assert normalize_skill_name("Database Management Systems") == "Database Management Systems"


def test_ml_draft_changes_with_prediction_payload():
    first = _ml_deterministic_draft(
        {"employee_context": "equipe de dados"},
        {
            "recommendations": [{"track": "Dados e Ciência de Dados", "compatibility": 0.8}],
            "recognized_skills": [{"input": "Python", "level": 4}],
            "priorities": [{"skill": "SQL", "gap": 2.0}],
            "uncertainty": {"level": "moderate"},
            "input_quality": {"coverage": 0.5},
            "unrecognized_skills": [{"input": "Docker"}],
        },
    )
    second = _ml_deterministic_draft(
        {"employee_context": "engenharia"},
        {
            "recommendations": [{"track": "Cibersegurança", "compatibility": 0.9}],
            "recognized_skills": [{"input": "Security", "level": 4}],
            "priorities": [{"skill": "Cloud", "gap": 1.0}],
            "uncertainty": {"level": "lower"},
            "input_quality": {"coverage": 1.0},
            "unrecognized_skills": [],
        },
    )
    assert first != second
    assert "Dados e Ciência de Dados" in first
    assert "Cibersegurança" in second
    assert "Docker" in first
