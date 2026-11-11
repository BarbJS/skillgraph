from src.observability import ObservabilityStore, TraceContext
from src.observability_ui import render_observability


class _MetricColumn:
    def __init__(self):
        self.calls = []

    def metric(self, label, value):
        self.calls.append((label, value))


class _StreamlitStub:
    def __init__(self):
        self.columns_created = []

    def columns(self, count):
        row = [_MetricColumn() for _ in range(count)]
        self.columns_created.extend(row)
        return row

    def metric(self, *args, **kwargs):
        pass

    def caption(self, *args, **kwargs):
        pass

    def header(self, *args, **kwargs):
        pass

    def button(self, *args, **kwargs):
        return False

    def subheader(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def dataframe(self, *args, **kwargs):
        pass

    def tabs(self, labels):
        return [self for _ in labels]

    def selectbox(self, *args, **kwargs):
        return ""

    def expander(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def json(self, *args, **kwargs):
        pass


class _LangfuseStatus:
    def __getitem__(self, key):
        return {"enabled": False, "initialized": False}.get(key, False)

    def get(self, key, default=None):
        return default


class _ObservabilityStub:
    def langfuse_status(self):
        return _LangfuseStatus()

    def refresh(self):
        pass

    def snapshot(self):
        return {
            "traces": 2,
            "latency_p95_ms": 123.456,
            "average_tokens": 11.234,
            "average_cost": 0.03456,
            "error_rate": 0.125,
            "timeout_rate": 0.5,
            "input_tokens": 20,
            "output_tokens": 10,
            "cost": 0.07,
        }

    def recent_trace_rows(self, limit=10):
        return []

    def service_metrics(self):
        return []

    def task_metrics(self):
        return []

    def recent_errors(self):
        return []


def test_dashboard_direct_metrics_use_at_most_one_decimal(monkeypatch):
    streamlit = _StreamlitStub()
    monkeypatch.setattr("src.observability_ui.st", streamlit)
    monkeypatch.setattr("src.observability_ui.OBSERVABILITY", _ObservabilityStub())

    render_observability()

    assert streamlit.columns_created[0].calls == [("Traces", 2)]
    assert streamlit.columns_created[1].calls == [("P95 (ms)", "123.5")]
    assert streamlit.columns_created[2].calls == [("Média de tokens", "11.2")]
    assert streamlit.columns_created[3].calls == [("Média de custo", "0.0")]
    assert streamlit.columns_created[4].calls == [("Erros", "12.5%")]
    assert streamlit.columns_created[5].calls == [("Timeouts", "50.0%")]




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


def test_snapshot_exposes_average_tokens_and_cost_per_trace():
    store = ObservabilityStore()
    store.traces = []
    for input_tokens, output_tokens, cost in ((10, 6, 0.02), (4, 2, 0.04)):
        trace = TraceContext("route", role="desenvolvedor", user_key="synthetic")
        with trace.span("step", "service") as span:
            span.set_usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
            )
        trace.finish()
        store.traces.append(trace.summary())

    snapshot = store.snapshot()

    assert snapshot["average_tokens"] == 11.0
    assert snapshot["average_cost"] == 0.03


def test_snapshot_averages_are_zero_without_traces():
    store = ObservabilityStore()
    store.traces = []

    snapshot = store.snapshot()

    assert snapshot["average_tokens"] == 0.0
    assert snapshot["average_cost"] == 0.0


def test_dashboard_rows_do_not_contain_raw_content():
    store = ObservabilityStore()
    trace = TraceContext("rag", role="desenvolvedor", user_key="synthetic")
    trace.spans.append(type("Span", (), {"name": "x", "duration_ms": 1, "input_tokens": 2, "output_tokens": 3, "cost": 0.0})())
    trace.finish()
    store.traces.append(trace.summary())
    row = store.recent_trace_rows()[0]
    assert "prompt" not in row
    assert "answer" not in row
