from __future__ import annotations

import pytest

from src.dify_client import DifyClient, DifyClientError


class FakeResponse:
    def __init__(self, lines: list[str], status_code: int = 200) -> None:
        self.lines = lines
        self.status_code = status_code

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def iter_lines(self, decode_unicode: bool = False):
        yield from self.lines

    def json(self):
        return {"message": "invalid key"}


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.payload = None

    def post(self, url, *, headers, json, stream, timeout):
        self.payload = {"url": url, "headers": headers, "json": json}
        return self.response


class SequenceSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = iter(responses)
        self.calls = 0

    def post(self, url, *, headers, json, stream, timeout):
        self.calls += 1
        return next(self.responses)


def _successful_events() -> list[str]:
    return [
        "event: message",
        'data: {"answer":"resposta"}',
        "",
        "event: message_end",
        'data: {"message_id":"m1"}',
        "",
    ]


def test_stream_chat_parses_dify_events_without_logging_key():
    events = [
        "event: message",
        'data: {"answer":"60 horas ","conversation_id":"c1"}',
        "",
        "event: message",
        'data: {"answer":"por ano."}',
        "",
        "event: message_end",
        'data: {"message_id":"m1","conversation_id":"c1"}',
        "",
    ]
    session = FakeSession(FakeResponse(events))
    client = DifyClient("http://localhost", "secret-key", "user", session=session)

    result = client.chat("Qual é a carga?", conversation_id="")

    assert result.answer == "60 horas por ano."
    assert result.conversation_id == "c1"
    assert result.message_id == "m1"
    assert session.payload["url"] == "http://localhost/v1/chat-messages"
    assert session.payload["headers"]["Authorization"] == "Bearer secret-key"
    assert session.payload["json"]["response_mode"] == "streaming"


def test_high_demand_workflow_is_retried_before_answer_is_streamed(monkeypatch):
    monkeypatch.setattr("src.dify_client.time.sleep", lambda _: None)
    failed = FakeResponse(
        [
            "event: workflow_finished",
            'data: {"status":"failed","error":"This model is currently experiencing high demand"}',
            "",
        ]
    )
    session = SequenceSession([failed, FakeResponse(_successful_events())])
    client = DifyClient(
        "https://api.dify.ai/v1",
        "secret-key",
        "user",
        session=session,
        max_retries=1,
        retry_backoff_seconds=0,
    )

    result = client.chat("pergunta")

    assert result.answer == "resposta"
    assert session.calls == 2


def test_transient_http_error_is_retried(monkeypatch):
    monkeypatch.setattr("src.dify_client.time.sleep", lambda _: None)
    session = SequenceSession(
        [FakeResponse([], status_code=503), FakeResponse(_successful_events())]
    )
    client = DifyClient(
        "http://localhost",
        "secret-key",
        "user",
        session=session,
        max_retries=1,
        retry_backoff_seconds=0,
    )

    result = client.chat("pergunta")

    assert result.answer == "resposta"
    assert session.calls == 2


def test_transient_failure_after_partial_answer_is_not_retried(monkeypatch):
    monkeypatch.setattr("src.dify_client.time.sleep", lambda _: None)
    partial_failure = FakeResponse(
        [
            "event: message",
            'data: {"answer":"parcial"}',
            "",
            "event: workflow_finished",
            'data: {"status":"failed","error":"high demand"}',
            "",
        ]
    )
    session = SequenceSession([partial_failure, FakeResponse(_successful_events())])
    client = DifyClient(
        "http://localhost",
        "secret-key",
        "user",
        session=session,
        max_retries=1,
        retry_backoff_seconds=0,
    )

    with pytest.raises(DifyClientError, match="high demand"):
        list(client.stream_chat("pergunta"))
    assert session.calls == 1


def test_dify_timeout_defaults_are_bounded(monkeypatch):
    monkeypatch.delenv("DIFY_CONNECT_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("DIFY_READ_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("DIFY_TOTAL_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("DIFY_MAX_RETRIES", raising=False)
    client = DifyClient("http://localhost", "key", "user")
    assert client.timeout == (10.0, 60.0)
    assert client.total_timeout_seconds == 120.0
    assert client.max_retries == 1


def test_dify_timeout_configuration_is_validated():
    with pytest.raises(DifyClientError, match="DIFY_TOTAL_TIMEOUT_SECONDS"):
        DifyClient("http://localhost", "key", "user", total_timeout_seconds=0)


def test_cloud_base_url_normalizes_api_path():
    session = FakeSession(
        FakeResponse(
            [
                "event: message",
                'data: {"answer":"resposta"}',
                "",
                "event: message_end",
                'data: {"message_id":"m1"}',
                "",
            ]
        )
    )
    client = DifyClient(
        "https://api.dify.ai/v1", "secret-key", "user", session=session
    )

    list(client.stream_chat("pergunta"))

    assert session.payload["url"] == "https://api.dify.ai/v1/chat-messages"


def test_chatflow_workflow_finished_output_is_used_when_no_message_chunk():
    events = [
        "event: workflow_finished",
        'data: {"status":"succeeded","outputs":{"answer":"Resposta do workflow"}}',
        "",
    ]
    session = FakeSession(FakeResponse(events))
    client = DifyClient(
        "https://api.dify.ai/v1", "secret-key", "user", session=session
    )

    result = client.chat("pergunta")

    assert result.answer == "Resposta do workflow"


def test_chatflow_workflow_failure_exposes_provider_detail():
    events = [
        "event: workflow_finished",
        'data: {"status":"failed","outputs":{},"error":"Gemini indisponível"}',
        "",
    ]
    session = FakeSession(FakeResponse(events))
    client = DifyClient(
        "https://api.dify.ai/v1", "secret-key", "user", session=session
    )

    with pytest.raises(DifyClientError, match="Gemini indisponível"):
        list(client.stream_chat("pergunta"))


def test_stream_chat_records_provider_usage_on_trace():
    events = [
        "event: message",
        'data: {"answer":"resposta"}',
        "",
        "event: message_end",
        'data: {"usage":{"prompt_tokens":12,"completion_tokens":7,"total_tokens":19,"cost":0.03}}',
        "",
    ]
    session = FakeSession(FakeResponse(events))
    from src.observability import TraceContext

    trace = TraceContext("rag", role="desenvolvedor", user_key="synthetic")
    client = DifyClient(
        "http://localhost", "secret-key", "user", session=session, trace=trace
    )
    list(client.stream_chat("pergunta"))
    trace.finish()
    summary = trace.summary()
    assert summary["input_tokens"] == 12
    assert summary["output_tokens"] == 7
    assert summary["cost"] == 0.03


def test_stream_chat_without_usage_keeps_cost_explicitly_unpriced():
    events = [
        "event: message",
        'data: {"answer":"resposta"}',
        "",
        "event: message_end",
        'data: {"message_id":"m1"}',
        "",
    ]
    session = FakeSession(FakeResponse(events))
    from src.observability import TraceContext

    trace = TraceContext("rag", role="desenvolvedor", user_key="synthetic")
    client = DifyClient(
        "http://localhost", "secret-key", "user", session=session, trace=trace
    )
    list(client.stream_chat("pergunta"))
    trace.finish()
    summary = trace.summary()
    assert summary["input_tokens"] > 0
    assert summary["output_tokens"] > 0
    assert summary["cost"] == 0.0
    assert trace.spans[0].metadata["usage_source"] == "local_estimate"


def test_empty_question_is_rejected():
    client = DifyClient("http://localhost", "secret-key", "user")
    with pytest.raises(DifyClientError, match="não pode ser vazia"):
        list(client.stream_chat("  "))


def test_auth_error_does_not_expose_secret():
    session = FakeSession(FakeResponse([], status_code=401))
    client = DifyClient("http://localhost", "secret-key", "user", session=session)
    with pytest.raises(DifyClientError) as error:
        list(client.stream_chat("pergunta"))
    assert "secret-key" not in str(error.value)
