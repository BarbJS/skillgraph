from src.alerting import AlertManager
from src.observability import TraceContext


def test_trace_summary_contains_required_metadata():
    trace = TraceContext("rag", role="desenvolvedor", user_key="user")
    with trace.span("retrieval", "dify", task_name="retrieve") as span:
        span.set_usage(input_tokens=10, output_tokens=4, cost=0.01)
    trace.finish()
    summary = trace.summary()
    assert summary["trace_id"]
    assert summary["timestamp"]
    assert summary["input_tokens"] == 10
    assert summary["output_tokens"] == 4
    assert summary["cost"] == 0.01
    assert summary["spans"][0]["task_name"] == "retrieve"


def test_alert_disabled_does_not_send(monkeypatch):
    monkeypatch.setenv("SLACK_ALERTS_ENABLED", "false")
    manager = AlertManager()
    assert manager.notify("critical", "test", {"trace_id": "x"}) is False


def test_slack_alert_uses_bot_token_without_sending_when_disabled(monkeypatch):
    monkeypatch.setenv("SLACK_ALERTS_ENABLED", "false")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-secret")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    assert AlertManager().notify("super_critical", "test", {"trace_id": "x"}) is False


def test_slack_alert_posts_sanitized_payload(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True}

    calls = []
    monkeypatch.setenv("SLACK_ALERTS_ENABLED", "true")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-secret")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    monkeypatch.setattr(
        "src.alerting.requests.post",
        lambda *args, **kwargs: (calls.append((args, kwargs)) or Response()),
    )
    assert (
        AlertManager().notify("critical", "latency", {"trace_id": "abc", "value": 99})
        is True
    )
    assert calls[0][0][0].endswith("chat.postMessage")
    assert calls[0][1]["json"]["channel"] == "C123"
    assert "xoxb-secret" not in str(calls[0][1]["json"])
