from src.observability import ObservabilityStore, TraceContext


def test_trace_summary_has_latency_tokens_and_cost():
    trace = TraceContext("test", role="desenvolvedor", user_key="synthetic")
    with trace.span("model", "llm", task_name="completion") as span:
        span.set_usage(input_tokens=10, output_tokens=5, cost=0.0)
    trace.finish()
    summary = trace.summary()
    assert summary["duration_ms"] >= 0
    assert summary["input_tokens"] == 10
    assert summary["output_tokens"] == 5
    assert summary["cost"] == 0.0


def test_langfuse_payload_is_aggregate_and_no_raw_content():
    class FakeObservation:
        def __init__(self):
            self.calls = []

        def update(self, **kwargs):
            self.calls.append(kwargs)

        def end(self):
            self.calls.append({"end": True})

    class FakeLangfuse:
        def __init__(self):
            self.observations = []

        def start_as_current_observation(self, **kwargs):
            obs = FakeObservation()
            self.observations.append((kwargs, obs))
            return obs

        def flush(self):
            pass

    store = ObservabilityStore.__new__(ObservabilityStore)
    store._langfuse = FakeLangfuse()
    trace = TraceContext("rag", role="desenvolvedor", user_key="synthetic")
    with trace.span("retrieval", "dify", task_name="stream") as span:
        span.set_usage(input_tokens=2, output_tokens=3, cost=0.0)
        span.metadata = {"prompt": "secret", "safe": "ok"}
    trace.finish()
    store._send_langfuse(trace)
    raw = str(store._langfuse.observations)
    calls = " ".join(str(obs.calls) for _, obs in store._langfuse.observations)
    assert "secret" not in raw + calls
    assert "input_tokens" in calls
    assert "output_tokens" in calls
    assert "duration_ms" in calls
    assert "cost" in calls
