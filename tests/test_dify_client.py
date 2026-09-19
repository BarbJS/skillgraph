from __future__ import annotations

import json

import pytest
import requests

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
        'event: message',
        'data: {"answer":"60 horas ","conversation_id":"c1"}',
        '',
        'event: message',
        'data: {"answer":"por ano."}',
        '',
        'event: message_end',
        'data: {"message_id":"m1","conversation_id":"c1"}',
        '',
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
