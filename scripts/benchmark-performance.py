#!/usr/bin/env python3
"""Measure clean-process startup time and peak RSS without private payloads."""

from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path


def _run(command: list[str], env: dict[str, str]) -> dict[str, float | int | str]:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    # ru_maxrss is cumulative for children in this parent process; the
    # benchmark runs each sample in a fresh worker to keep samples comparable.
    peak_rss_kb = int(usage.ru_maxrss)
    if sys.platform == "darwin":
        peak_rss_kb //= 1024
    return {
        "command": " ".join(command),
        "elapsed_ms": round(elapsed_ms, 1),
        "peak_rss_mb": round(peak_rss_kb / 1024, 1),
        "returncode": completed.returncode,
        "stderr_tail": completed.stderr[-300:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--streamlit", action="store_true")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs deve ser >= 1")

    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["STARTUP_PROFILE"] = "false"
    if args.streamlit:
        env["STREAMLIT_PORT"] = "8515"
        command = [str(root / "scripts/start-crewai-streamlit.sh")]
    else:
        command = [
            sys.executable,
            "-c",
            "import app; print('import-ok')",
        ]

    results = [_run(command, env) for _ in range(args.runs)]
    print(json.dumps({"runs": results}, ensure_ascii=False, indent=2))
    return 0 if all(item["returncode"] == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
