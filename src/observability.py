"""Privacy-preserving Langfuse-compatible traces and operational metrics."""

from __future__ import annotations
import contextvars
import hashlib
import json
import os
import statistics
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from src.alerting import AlertManager

LOG_PATH = Path(os.getenv("OBSERVABILITY_LOG_PATH", "logs/observability.jsonl"))
_CURRENT_TRACE: contextvars.ContextVar["TraceContext | None"] = contextvars.ContextVar(
    "skillgraph_trace", default=None
)


def current_trace() -> "TraceContext | None":
    return _CURRENT_TRACE.get()


def _enabled() -> bool:
    return os.getenv("LANGFUSE_ENABLED", "false").casefold() == "true"


def anonymous_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _write_local_trace(summary: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(summary, ensure_ascii=False, default=str) + "\n")


@dataclass
class SpanRecord:
    trace_id: str
    span_id: str
    parent_id: str | None
    name: str
    service: str
    task_name: str | None
    started_at: str
    duration_ms: float = 0.0
    status: str = "running"
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class TraceContext:
    def __init__(self, route: str, *, role: str = "", user_key: str = ""):
        self.trace_id = str(uuid.uuid4())
        self.route = route
        self.role = role
        self.user_id = anonymous_id(user_key or role or "anonymous")
        self.started = time.perf_counter()
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.spans = []
        self.status = "running"
        self.error = None
        self._token = None

    def __enter__(self):
        self._token = _CURRENT_TRACE.set(self)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.finish("error" if exc else "success", str(exc) if exc else None)
        OBSERVABILITY.record(self)
        _CURRENT_TRACE.reset(self._token) if self._token else None

    def span(self, name, service, *, task_name=None, metadata=None):
        return SpanContext(self, name, service, task_name, metadata or {})

    def finish(self, status="success", error=None):
        if self.status != "running":
            return
        self.status = status
        self.error = error
        self.spans.append(
            SpanRecord(
                self.trace_id,
                str(uuid.uuid4()),
                None,
                "trace",
                "system",
                None,
                self.started_at,
                (time.perf_counter() - self.started) * 1000,
                status,
                error=error,
            )
        )

    def summary(self):
        durations = [s.duration_ms for s in self.spans if s.name != "trace"]
        return {
            "trace_id": self.trace_id,
            "timestamp": self.started_at,
            "route": self.route,
            "role": self.role,
            "user_id": self.user_id,
            "status": self.status,
            "error": self.error,
            "span_count": len(durations),
            "duration_ms": round((time.perf_counter() - self.started) * 1000, 2),
            "span_duration_ms": round(sum(durations), 2),
            "input_tokens": sum(s.input_tokens for s in self.spans),
            "output_tokens": sum(s.output_tokens for s in self.spans),
            "cost": round(sum(s.cost for s in self.spans), 8),
            "spans": [s.__dict__ for s in self.spans],
        }


class SpanContext:
    def __init__(self, trace, name, service, task_name, metadata):
        self.trace = trace
        self.name = name
        self.service = service
        self.task_name = task_name
        self.metadata = metadata
        self.started = time.perf_counter()
        self._usage = (0, 0, 0.0)

    def __enter__(self):
        return self

    def set_usage(self, *, input_tokens=0, output_tokens=0, cost=0.0):
        self._usage = (input_tokens, output_tokens, cost)

    def __exit__(self, exc_type, exc, tb):
        i, o, c = self._usage
        self.trace.spans.append(
            SpanRecord(
                self.trace.trace_id,
                str(uuid.uuid4()),
                None,
                self.name,
                self.service,
                self.task_name,
                datetime.now(timezone.utc).isoformat(),
                (time.perf_counter() - self.started) * 1000,
                "error" if exc else "success",
                i,
                o,
                c,
                str(exc) if exc else None,
                self.metadata,
            )
        )


class ObservabilityStore:
    def __init__(self):
        self.traces = []
        self.alert_manager = AlertManager()
        self._langfuse = None
        if _enabled():
            try:
                from langfuse import Langfuse

                self._langfuse = Langfuse()
            except Exception:
                self._langfuse = None

    def record(self, trace):
        summary = trace.summary()
        self.traces = (self.traces + [summary])[-500:]
        _write_local_trace(summary)
        self._check_alerts(summary)
        if self._langfuse:
            self._send_langfuse(trace)

    def _check_alerts(self, s):
        if s.get("status") == "error":
            self.alert_manager.notify(
                "high",
                "SkillGraph request failed",
                {"trace_id": s["trace_id"], "route": s["route"]},
            )
        if float(s.get("duration_ms", 0)) > float(
            os.getenv("OBS_P95_ALERT_MS", "5000")
        ):
            self.alert_manager.notify(
                "critical",
                "SkillGraph latency threshold exceeded",
                {"trace_id": s["trace_id"], "duration_ms": s["duration_ms"]},
            )

    def _send_langfuse(self, trace):
        try:
            root = self._langfuse.start_as_current_observation(
                name=trace.route,
                as_type="span",
                metadata={"role": trace.role, "user_id": trace.user_id},
                input={"route": trace.route},
            )
            for s in trace.spans:
                if s.name != "trace":
                    root.update(
                        metadata={
                            "last_span": s.name,
                            "service": s.service,
                            "task_name": s.task_name,
                            "status": s.status,
                            "duration_ms": s.duration_ms,
                        }
                    )
            root.update(output={"status": trace.status, "trace_id": trace.trace_id})
            root.end()
            self._langfuse.flush()
        except Exception:
            pass

    def record_feedback(self, *, trace_id, message_id, rating, route):
        for t in self.traces:
            if t.get("trace_id") == trace_id:
                t.setdefault("feedback", []).append(
                    {"message_id": message_id, "rating": rating, "route": route}
                )
        if self._langfuse:
            try:
                self._langfuse.create_score(
                    trace_id=trace_id,
                    name="user_feedback",
                    value=float(rating),
                    data_type="NUMERIC",
                    comment=f"route={route}",
                )
                self._langfuse.flush()
            except Exception:
                pass

    def _group_metrics(self, key: str) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for trace in self.traces:
            for span in trace.get("spans", []):
                value = span.get(key) or "unknown"
                groups.setdefault(str(value), []).append(span)
        rows = []
        for value, spans in sorted(groups.items()):
            durations = [float(x.get("duration_ms", 0)) for x in spans]
            errors = sum(x.get("status") == "error" for x in spans)
            rows.append(
                {
                    "name": value,
                    "count": len(spans),
                    "error_rate": round(errors / len(spans), 4) if spans else 0.0,
                    "latency_avg_ms": (
                        round(sum(durations) / len(durations), 2) if durations else 0.0
                    ),
                    "latency_p95_ms": (
                        round(
                            statistics.quantiles(durations, n=20, method="inclusive")[
                                18
                            ],
                            2,
                        )
                        if len(durations) > 1
                        else (round(durations[0], 2) if durations else 0.0)
                    ),
                    "input_tokens": sum(x.get("input_tokens", 0) for x in spans),
                    "output_tokens": sum(x.get("output_tokens", 0) for x in spans),
                    "cost": round(sum(x.get("cost", 0) for x in spans), 8),
                }
            )
        return rows

    def service_metrics(self) -> list[dict[str, Any]]:
        return self._group_metrics("service")

    def task_metrics(self) -> list[dict[str, Any]]:
        return self._group_metrics("task_name")

    def recent_errors(self) -> list[dict[str, Any]]:
        return [
            trace
            for trace in self.traces
            if trace.get("status") in {"error", "timeout"}
        ][-50:]

    def snapshot(self):
        ts = self.traces
        vals = [float(t.get("duration_ms", 0)) for t in ts]

        def pct(q):
            return (
                round(
                    statistics.quantiles(vals, n=100, method="inclusive")[
                        max(0, int(q * 100) - 1)
                    ],
                    2,
                )
                if len(vals) > 1
                else (round(vals[0], 2) if vals else 0.0)
            )

        return {
            "traces": len(ts),
            "latency_p50_ms": pct(0.5),
            "latency_p95_ms": pct(0.95),
            "latency_p99_ms": pct(0.99),
            "error_rate": (
                round(sum(t.get("status") == "error" for t in ts) / len(ts), 4)
                if ts
                else 0.0
            ),
            "timeout_rate": (
                round(sum(t.get("status") == "timeout" for t in ts) / len(ts), 4)
                if ts
                else 0.0
            ),
            "input_tokens": sum(t.get("input_tokens", 0) for t in ts),
            "output_tokens": sum(t.get("output_tokens", 0) for t in ts),
            "cost": round(sum(t.get("cost", 0) for t in ts), 8),
            "recent_traces": ts[-20:],
        }


OBSERVABILITY = ObservabilityStore()
