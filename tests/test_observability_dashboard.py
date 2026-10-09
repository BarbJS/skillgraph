from src.observability import ObservabilityStore, TraceContext


def test_recent_trace_rows_are_limited_and_identifiable():
    store = ObservabilityStore()
    for index in range(12):
        trace = TraceContext(f"route-{index}", role="desenvolvedor", user_key=f"user-{index}")
        with trace.span("step", "service", task_name="task") as span:
            span.set_usage(input_tokens=index, output_tokens=index + 1, cost=0.0)
        trace.finish()
        store.traces.append(trace.summary())
    rows = store.recent_trace_rows(limit=10)
    assert len(rows) == 10
    assert rows[0]["Rota"] == "route-11"
    assert rows[0]["Trace ID"]
    assert rows[0]["Tokens entrada"] == 11
    assert store.get_trace(rows[0]["Trace ID"])["route"] == "route-11"


def test_dashboard_rows_do_not_contain_raw_content():
    store = ObservabilityStore()
    trace = TraceContext("rag", role="desenvolvedor", user_key="synthetic")
    trace.spans.append(type("Span", (), {"name": "x", "duration_ms": 1, "input_tokens": 2, "output_tokens": 3, "cost": 0.0})())
    trace.finish()
    store.traces.append(trace.summary())
    row = store.recent_trace_rows()[0]
    assert "prompt" not in row
    assert "answer" not in row
