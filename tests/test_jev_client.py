from src.jev_client import JevClient, JevError


class Response:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return {
            "model": "jev-1.13.0",
            "answers": {"x": {"type": "noul", "noul": 1.0}},
            "usage": {"input_tokens": 1},
        }


class Session:
    def __init__(self):
        self.payload = None

    def post(self, url, **kwargs):
        self.payload = (url, kwargs)
        return Response()


def test_disabled_jev_does_not_call_external_service():
    try:
        JevClient(enabled=False, session=Session()).analyze(
            "state", {"x": {"type": "noul", "instructions": "x"}}
        )
    except JevError as exc:
        assert "desativado" in str(exc)
    else:
        raise AssertionError("disabled JEV should fail safely")


def test_enabled_jev_builds_systemone_payload():
    session = Session()
    result = JevClient(enabled=True, api_key="test", session=session).analyze(
        {"resume": "text"}, {"x": {"type": "noul", "instructions": "x"}}
    )
    assert result.answers["x"]["noul"] == 1.0
    assert session.payload[0].endswith("/systemone")
    assert session.payload[1]["json"]["model"] == "jev-latest"


def test_jev_diagnostics_never_exposes_api_key():
    result = JevClient(enabled=True, api_key="secret-key").diagnostics()
    assert result["configured"] is True
    assert "secret-key" not in str(result)


def test_jev_rejects_protected_pii_before_request():
    session = Session()
    try:
        JevClient(enabled=True, api_key="test", session=session).analyze(
            {"document_text": "contato pessoa@example.com"}, {"x": {"type": "noul"}}
        )
    except JevError as exc:
        assert "dados pessoais" in str(exc)
    else:
        raise AssertionError("JEV must reject PII before sending")
    assert session.payload is None
