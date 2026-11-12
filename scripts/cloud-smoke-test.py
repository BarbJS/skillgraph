#!/usr/bin/env python3
"""Validate a deployed Streamlit health endpoint."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="URL pública da aplicação")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    health_url = f"{base}/_stcore/health"
    try:
        with urllib.request.urlopen(health_url, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
            if response.status != 200:
                raise RuntimeError(f"health check retornou HTTP {response.status}")
    except (OSError, urllib.error.URLError, RuntimeError) as exc:
        print(json.dumps({"url": health_url, "healthy": False, "error": str(exc)}))
        return 1
    print(json.dumps({"url": health_url, "healthy": True, "body": body[:200]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
