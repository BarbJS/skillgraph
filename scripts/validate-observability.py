#!/usr/bin/env python3
"""Send one synthetic, non-PII trace to configured Langfuse and Slack alert sink."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
load_dotenv(ROOT / ".env")

from src.alerting import AlertManager
from src.observability import OBSERVABILITY, TraceContext


def main() -> None:
    trace = TraceContext(
        "observability_validation",
        role="desenvolvedor",
        user_key="synthetic-validation",
    )
    with trace.span("synthetic_router", "validation", task_name="route") as span:
        span.set_usage(input_tokens=12, output_tokens=8, cost=0.0)
    with trace.span("synthetic_model", "validation", task_name="response") as span:
        span.set_usage(input_tokens=20, output_tokens=15, cost=0.0)
    trace.finish("success")
    OBSERVABILITY.record(trace)
    slack = AlertManager()
    print(
        {
            "trace_id": trace.trace_id,
            "langfuse_enabled": bool(os.getenv("LANGFUSE_ENABLED")),
            "slack_enabled": bool(os.getenv("SLACK_ALERTS_ENABLED")),
            "local_recorded": True,
        }
    )
    if slack.enabled:
        print(
            {
                "slack_alert_sent": slack.notify(
                    "high",
                    "Synthetic observability validation",
                    {"trace_id": trace.trace_id, "note": "no PII; validation only"},
                )
            }
        )
    print({"metrics": OBSERVABILITY.snapshot()})


if __name__ == "__main__":
    main()
