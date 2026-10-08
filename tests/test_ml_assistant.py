import json

from src.ml_assistant import LocalMLAssistant, MLAssistantError, _coerce_profile


class FakeResponse:
    def __init__(self, body, status_code=200):
        self.body = body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("fake error")

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.payloads = []

    def post(self, url, **kwargs):
        self.payloads.append(kwargs["json"])
        return FakeResponse(self.responses.pop(0))


def test_profile_validation_is_for_collaborator_not_user():
    profile = _coerce_profile(
        {
            "employee_context": "colaborador da equipe de dados",
            "skills": {"Python": 4, "SQL": 3},
            "goal": "trilha",
        }
    )
    assert profile["employee_context"] == "colaborador da equipe de dados"
    assert profile["skills"]["Programming"] == 4


def test_profile_rejects_personal_identifiers():
    try:
        _coerce_profile({"employee_context": "CPF 123", "skills": {"Python": 4}})
    except MLAssistantError as exc:
        assert "identificador" in str(exc)
    else:
        raise AssertionError("PII should be rejected")


def test_natural_language_route_returns_backend_recommendation(tmp_path, monkeypatch):
    artifact = tmp_path / "skillgraph_competency_tracks.pkl"
    artifact.write_bytes(b"placeholder")
    session = FakeSession(
        [
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "action": "recommend_track",
                                    "employee_context": "colaborador da equipe de dados",
                                    "skills": {"Python": 4, "SQL": 3},
                                    "goal": "desenvolvimento",
                                }
                            )
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "message": {
                            "content": "A trilha recomendada é Dados e Ciência de Dados."
                        }
                    }
                ]
            },
        ]
    )
    import src.ml_assistant as assistant_module

    monkeypatch.setattr(assistant_module, "load_artifact", lambda path: {"ok": True})
    monkeypatch.setattr(
        assistant_module,
        "recommend_from_profile",
        lambda path, skills: {
            "recommendations": [
                {"track": "Dados e Ciência de Dados", "compatibility": 0.8}
            ],
            "priorities": [],
            "skills_received": skills,
            "recognized_skills": skills,
        },
    )
    result = LocalMLAssistant(artifact, session=session).predict_from_question(
        "O colaborador de dados tem Python avançado e SQL intermediário. Qual trilha?"
    )
    assert result.recommendations[0]["track"] == "Dados e Ciência de Dados"
    assert result.structured["recommendations"] == result.recommendations
    assert "Dados" in result.answer
