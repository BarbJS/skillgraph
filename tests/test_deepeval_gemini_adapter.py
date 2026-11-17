import json

import requests

from src.deepeval_judge import LocalDeepEvalModel


class StructuredSchema:
    @classmethod
    def model_json_schema(cls):
        return {
            "$defs": {
                "Verdict": {
                    "type": "object",
                    "properties": {
                        "verdict": {"type": "string", "enum": ["yes", "no"]},
                        "reason": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "default": None,
                        },
                    },
                    "required": ["verdict"],
                }
            },
            "type": "object",
            "properties": {
                "verdicts": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/Verdict"},
                }
            },
            "required": ["verdicts"],
        }

    @classmethod
    def model_validate(cls, value):
        return value


class Response:
    def __init__(self, payload, status_code=200, text=""):
        self.payload = payload
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        return self.payload


class ErrorSession:
    def post(self, url, **kwargs):
        return Response(
            {"error": {"message": "responseSchema has invalid type"}},
            status_code=400,
        )


class StructuredSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(
            {
                "candidates": [
                    {"content": {"parts": [{"text": '{"verdicts": []}'}]}}
                ]
            }
        )


class Session:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(
            {
                "candidates": [
                    {"content": {"parts": [{"text": "judge output"}]}}
                ],
                "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2},
            }
        )




def test_judge_translates_pydantic_schema_to_gemini_schema():
    session = StructuredSession()
    judge = LocalDeepEvalModel(api_key="judge-key", session=session)
    assert judge.generate("evaluate", schema=StructuredSchema) == {"verdicts": []}
    url, kwargs = session.calls[0]
    assert "judge-key" not in url
    assert kwargs["headers"]["x-goog-api-key"] == "judge-key"
    schema = kwargs["json"]["generationConfig"]["responseSchema"]
    assert schema["type"] == "OBJECT"
    assert schema["properties"]["verdicts"]["type"] == "ARRAY"
    verdict = schema["properties"]["verdicts"]["items"]
    assert verdict["type"] == "OBJECT"
    assert verdict["properties"]["reason"] == {"type": "STRING", "nullable": True}
    assert "$defs" not in json.dumps(schema)


def test_judge_sanitizes_http_errors():
    judge = LocalDeepEvalModel(api_key="judge-key", session=ErrorSession())
    try:
        judge.generate("evaluate")
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected Gemini HTTP error")
    assert "400" in message
    assert "responseSchema has invalid type" in message
    assert "judge-key" not in message


def test_judge_uses_google_gemini_endpoint(monkeypatch):
    session = Session()
    monkeypatch.setenv("EVAL_JUDGE_API_KEY", "judge-key")
    judge = LocalDeepEvalModel(session=session)
    assert judge.generate("evaluate") == "judge output"
    assert session.calls[0][0].endswith("/models/gemini-3.1-flash-lite:generateContent")
    assert session.calls[0][1]["headers"]["x-goog-api-key"] == "judge-key"
    assert "params" not in session.calls[0][1]
    assert judge.last_usage["promptTokenCount"] == 3
