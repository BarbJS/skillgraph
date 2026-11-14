from src.observability import ObservabilityStore, TraceContext, _safe_metadata


def test_metadata_redacts_private_content():
    safe = _safe_metadata({"prompt": "secret", "answer": "private", "model": "gemini-3.1-flash-lite", "route": "rag"})
    assert "prompt" not in safe
    assert "answer" not in safe
    assert safe["model"] == "gemini-3.1-flash-lite"
    assert safe["route"] == "rag"


def test_langfuse_send_uses_sanitized_root_and_flush(monkeypatch):
    class Child:
        def __init__(self): self.ended = False
        def update(self, **kwargs): pass
        def end(self): self.ended = True
    class Root(Child):
        def start_span(self, **kwargs): return Child()
        def start_generation(self, **kwargs): return Child()
    class FakeLangfuse:
        def __init__(self, **kwargs): self.kwargs = kwargs; self.root = Root(); self.flushed = False
        def start_span(self, **kwargs): self.root.kwargs = kwargs; return self.root
        def flush(self): self.flushed = True
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
    store = ObservabilityStore()
    fake = FakeLangfuse()
    store._langfuse = fake
    trace = TraceContext("competency_development_rag", role="desenvolvedor", user_key="user")
    with trace.span("gemini.final_synthesis", "gemini", task_name="final_synthesis", metadata={"model": "gemini-3.1-flash-lite", "prompt": "private"}) as span:
        span.set_usage(input_tokens=2, output_tokens=3, cost=0.01)
    trace.finish("success")
    store._send_langfuse(trace)
    assert fake.flushed is True
    assert fake.root.kwargs["input"] == {"route": "competency_development_rag"}
    assert fake.root.kwargs["metadata"]["span_names"] == ["gemini.final_synthesis"]
