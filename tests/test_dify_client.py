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
