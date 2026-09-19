"""Privacy-preserving metrics and JSONL event recorder."""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


@dataclass
class MetricsStore:
    total_requests: int = 0
    blocked_requests: int = 0
    errors: int = 0
    total_latency_ms: float = 0.0
    sources_seen: int = 0
    tools_seen: int = 0
    routes: Counter[str] = field(default_factory=Counter)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def record(
        self,
        *,
        route: str,
        latency_ms: float,
        blocked: bool = False,
        error: bool = False,
        sources_count: int = 0,
        tools_count: int = 0,
    ) -> None:
        with self._lock:
            self.total_requests += 1
            self.total_latency_ms += latency_ms
            self.routes[route] += 1
            self.blocked_requests += int(blocked)
            self.errors += int(error)
            self.sources_seen += sources_count
            self.tools_seen += tools_count

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_requests": self.total_requests,
                "blocked_requests": self.blocked_requests,
                "errors": self.errors,
                "average_latency_ms": round(self.total_latency_ms / self.total_requests, 2) if self.total_requests else 0.0,
                "sources_seen": self.sources_seen,
                "tools_seen": self.tools_seen,
                "routes": dict(self.routes),
                "block_rate": round(self.blocked_requests / self.total_requests, 4) if self.total_requests else 0.0,
            }

    def reset(self) -> None:
        with self._lock:
            self.total_requests = 0
            self.blocked_requests = 0
            self.errors = 0
            self.total_latency_ms = 0.0
            self.sources_seen = 0
            self.tools_seen = 0
            self.routes.clear()


METRICS = MetricsStore()


def record_event(
    log_path: str | Path,
    *,
    request_id: str,
    route: str,
    status: str,
    latency_ms: float,
    blocked: bool = False,
    error: bool = False,
    tools: list[str] | None = None,
    sources_count: int = 0,
) -> None:
    """Record metadata only; never write full questions, answers, or secrets."""

    tool_names = tools or []
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "route": route,
        "status": status,
        "latency_ms": round(latency_ms, 2),
        "blocked": blocked,
        "error": error,
        "tools": tool_names,
        "sources_count": sources_count,
    }
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    METRICS.record(
        route=route,
        latency_ms=latency_ms,
        blocked=blocked,
        error=error,
        sources_count=sources_count,
        tools_count=len(tool_names),
    )


class Timer:
    def __enter__(self) -> "Timer":
        self.started = time.perf_counter()
        return self

    def __exit__(self, *_args: object) -> None:
        self.elapsed_ms = (time.perf_counter() - self.started) * 1000
