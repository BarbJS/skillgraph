#!/usr/bin/env python3
"""Generate five synthetic, non-PII traces for the Langfuse demonstration."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
load_dotenv(ROOT / ".env")

from src.observability import OBSERVABILITY, TraceContext


CASES = (
    ("rag", "dify", "stream_chat"),
    ("structured_data", "duckdb", "answer_structured_question"),
    ("training_recommendation", "crewai", "training_route"),
    ("policy_rag", "dify", "policy_route"),
    ("resume_analysis", "ocr", "pdf_text_extraction"),
)


def main() -> None:
    trace_ids = []
    for index, (route, service, task) in enumerate(CASES, start=1):
        trace = TraceContext(
            route,
            role="desenvolvedor",
            user_key=f"synthetic-langfuse-demo-{index}",
        )
        with trace.span(
            f"demo.{service}",
            service,
            task_name=task,
            metadata={"demo": "langfuse-five-traces"},
        ) as span:
            span.set_usage(input_tokens=10 + index, output_tokens=6 + index, cost=0.0)
        trace.finish("success")
        OBSERVABILITY.record(trace)
        trace_ids.append(trace.trace_id)

    print({
        "generated": len(trace_ids),
        "trace_ids": trace_ids,
        "langfuse_enabled": os.getenv("LANGFUSE_ENABLED", "false"),
        "local_log": str(OBSERVABILITY_LOG_PATH),
    })


OBSERVABILITY_LOG_PATH = os.getenv("OBSERVABILITY_LOG_PATH", "logs/observability.jsonl")


if __name__ == "__main__":
    main()
