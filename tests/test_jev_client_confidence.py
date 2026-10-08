from src.jev_client import JevClient


class Response:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return {
            "model": "jev-1.13.0",
            "answers": {
                "a": {"type": "choice", "confidence": 0.8},
                "b": {"type": "noul", "noul": 0.6},
            },
            "usage": {"input_tokens": 2, "output_tokens": 1},
        }


class Session:
    def post(self, *a, **k):
        return Response()


def test_jev_confidence_is_extracted():
    r = JevClient(enabled=True, api_key="x", session=Session()).analyze(
        "synthetic", {"a": {"type": "choice"}, "b": {"type": "noul"}}
    )
    assert r.confidence_by_question == {"a": 0.8, "b": 0.6}
    assert r.confidence_mean == 0.7
    assert r.confidence_min == 0.6
