#!/usr/bin/env python3
"""Send one real SDK trace and print only sanitized delivery status."""
from __future__ import annotations

import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src.observability import OBSERVABILITY, TraceContext


def main() -> None:
    trace = TraceContext(
        "langfuse_connection_test",
        role="desenvolvedor",
        user_key="connection-test",
    )
    with trace.span("connection_test", "validation", task_name="langfuse") as span:
        span.set_usage(input_tokens=1, output_tokens=1, cost=0.0)
    trace.finish("success")
    OBSERVABILITY.record(trace)
    status = OBSERVABILITY.langfuse_status()
    if OBSERVABILITY._langfuse:
        try:
            status["auth_check"] = OBSERVABILITY._langfuse.auth_check()
        except Exception as exc:
            status["auth_check"] = type(exc).__name__
    print(status)


if __name__ == "__main__":
    main()
