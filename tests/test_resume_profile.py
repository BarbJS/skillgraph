import json

from src.resume_profile import extract_profile


class Response:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "employee_context": "colaborador da equipe de dados",
                                        "skills": [
                                            {
                                                "name": "Python",
                                                "level": 4,
                                                "confidence": 0.9,
                                                "evidence": "Python avançado",
                                            }
                                        ],
                                        "unrecognized_skills": [],
                                        "missing_information": [],
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        ]
                    }
                }
            ]
        }


class Session:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response()


def test_resume_profile_uses_gemini_provider_when_configured(monkeypatch):
    session = Session()
    monkeypatch.setenv("RESUME_PROFILE_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    monkeypatch.setattr("src.resume_profile.requests.post", session.post)

    profile = extract_profile("Python avançado", {"response": {}})

    assert profile.skills[0].name == "Python"
    assert session.calls[0][0].endswith(
        "/models/gemini-3.1-flash-lite:generateContent"
    )
    assert session.calls[0][1]["params"] == {"key": "synthetic-key"}


def test_resume_profile_keeps_openai_compatible_local_provider(monkeypatch):
    session = Session()
    monkeypatch.setenv("RESUME_PROFILE_PROVIDER", "openai_compatible")
    monkeypatch.setenv("RESUME_PROFILE_BASE_URL", "http://lm-studio.test/v1")
    monkeypatch.setenv("RESUME_PROFILE_MODEL", "local-model")
    response = Response()
    response.json = lambda: {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "employee_context": "colaborador",
                            "skills": [],
                            "unrecognized_skills": [],
                            "missing_information": [],
                        }
                    )
                }
            }
        ]
    }
    session.post = lambda url, **kwargs: response
    monkeypatch.setattr("src.resume_profile.requests.post", session.post)
    profile = extract_profile("Python", {})

    assert profile.employee_context == "colaborador"
