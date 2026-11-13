from src.observability import ObservabilityStore, TraceContext, _langfuse_options


def test_langfuse_options_support_base_url_and_fast_flush(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "secret")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://hipaa.example")
    options = _langfuse_options()
    assert options["base_url"] == "https://hipaa.example"
    assert options["flush_at"] == 1
    assert options["flush_interval"] == 0.5
    assert options["tracing_enabled"] is True



def test_langfuse_options_fallback_to_host(monkeypatch):
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)
    monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.example")
    assert _langfuse_options()["base_url"] == "https://cloud.example"


# Existing sanitization tests continue below.



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

        def start_span(self, **kwargs):
            obs = FakeObservation()
            self.observations.append((kwargs, obs))
            return obs

        def flush(self):
            pass

    def start_span(self, **kwargs):
        child = FakeObservation()
        self.calls.append({"child": kwargs})
        return child

    FakeObservation.start_span = start_span

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
    calls += " " + str(store._langfuse.observations[0][0])
    calls += " " + str(store._langfuse.observations[0][1].calls)
    assert "secret" not in raw + calls
    assert "input_tokens" in calls
    assert "output_tokens" in calls
    assert "duration_ms" in calls
    assert "cost" in calls


def test_langfuse_generation_payload_uses_usage_and_cost():
    class FakeGeneration:
        def __init__(self, kwargs):
            self.kwargs = kwargs

        def end(self):
            pass

    class FakeObservation:
        def __init__(self, name):
            self.name = name
            self.calls = []

        def update(self, **kwargs):
            self.calls.append(kwargs)

        def start_generation(self, **kwargs):
            self.calls.append({"generation": kwargs})
            return FakeGeneration(kwargs)

        def end(self):
            pass

    class FakeLangfuse:
        def __init__(self):
            self.root = None
            self.flushed = False

        def start_span(self, **kwargs):
            self.root = FakeObservation(kwargs["name"])
            return self.root

        def flush(self):
            self.flushed = True

    store = ObservabilityStore.__new__(ObservabilityStore)
    store._langfuse = FakeLangfuse()
    trace = TraceContext("resume_analysis", role="desenvolvedor", user_key="synthetic")
    with trace.span(
        "gemini.final_synthesis",
        "gemini",
        task_name="final_synthesis",
        metadata={"observation_type": "generation", "model": "gemini-3.8-flash"},
    ) as span:
        span.set_usage(input_tokens=10, output_tokens=6, cost=0.000022)
    trace.finish()
    store._send_langfuse(trace)
    generation = next(item["generation"] for item in store._langfuse.root.calls if "generation" in item)
    assert generation["model"] == "gemini-3.8-flash"
    assert generation["usage_details"] == {"input": 10, "output": 6, "total": 16}
    assert generation["cost_details"] == {"total": 0.000022}


def test_langfuse_sdk3_payload_uses_real_span_lifecycle():
    class FakeObservation:
        def __init__(self, name):
            self.name = name
            self.calls = []
            self.children = []

        def update(self, **kwargs):
            self.calls.append(kwargs)

        def start_span(self, *, name, **kwargs):
            child = FakeObservation(name)
            self.children.append((kwargs, child))
            return child

        def end(self):
            self.calls.append({"end": True})

    class FakeLangfuse:
        def __init__(self):
            self.root = None
            self.flushed = False

        def start_span(self, *, name, **kwargs):
            self.root = FakeObservation(name)
            return self.root

        def flush(self):
            self.flushed = True

    store = ObservabilityStore.__new__(ObservabilityStore)
    store._langfuse = FakeLangfuse()
    trace = TraceContext("competency_development_rag", role="desenvolvedor", user_key="synthetic")
    with trace.span("tool.rag", "dify", task_name="DifyPolicyTool"):
        pass
    trace.finish()
    store._send_langfuse(trace)

    assert store._langfuse.root.name == "competency_development_rag"
    assert store._langfuse.root.children[0][1].name == "tool.rag"
    assert store._langfuse.root.calls[-1] == {"end": True}
    assert store._langfuse.root.children[0][1].calls[-1] == {"end": True}
    assert store._langfuse.flushed is True


def test_langfuse_is_not_initialized_when_store_is_created(monkeypatch):
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    store = ObservabilityStore()
    assert store._langfuse is None


def test_langfuse_initializes_on_first_record(monkeypatch):
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    store = ObservabilityStore()

    class FakeLangfuse:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setitem(__import__("sys").modules, "langfuse", type("Module", (), {"Langfuse": FakeLangfuse}))
    store._send_langfuse = lambda trace: None
    trace = TraceContext("test", role="desenvolvedor", user_key="synthetic")
    trace.finish()
    store.record(trace)
    assert isinstance(store._langfuse, FakeLangfuse)
