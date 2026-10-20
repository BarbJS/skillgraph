from src.dify_client import DifyClient
from src.observability import TraceContext


class FakeResponse:
    status_code = 200
    headers = {}

    def __init__(self, lines):
        self.lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def iter_lines(self, decode_unicode=False):
        yield from self.lines


class FakeSession:
    def __init__(self, lines):
        self.response = FakeResponse(lines)

    def post(self, *args, **kwargs):
        return self.response


def test_dify_usage_estimates_when_provider_omits_usage():
    session = FakeSession([
        "event: message",
        'data: {"answer":"resposta curta"}',
        "",
        "event: message_end",
        'data: {"message_id":"m1"}',
        "",
    ])
    trace = TraceContext("rag", role="desenvolvedor", user_key="synthetic")
    client = DifyClient("http://localhost", "key", "user", session=session, trace=trace)
    list(client.stream_chat("uma pergunta de teste"))
    trace.finish()
    summary = trace.summary()
    assert summary["input_tokens"] > 0
    assert summary["output_tokens"] > 0
    assert trace.spans[0].metadata["usage_source"] == "local_estimate"
    assert summary["cost"] == 0.0


def test_dify_usage_coerces_string_values():
    session = FakeSession([
        "event: message",
        'data: {"answer":"resposta"}',
        "",
        "event: message_end",
        'data: {"usage":{"prompt_tokens":"10","completion_tokens":"4","cost":"0.25"}}',
        "",
    ])
    trace = TraceContext("rag", role="desenvolvedor", user_key="synthetic")
    client = DifyClient("http://localhost", "key", "user", session=session, trace=trace)
    list(client.stream_chat("pergunta"))
    trace.finish()
    summary = trace.summary()
    assert summary["input_tokens"] == 10
    assert summary["output_tokens"] == 4
    assert summary["cost"] == 0.25
