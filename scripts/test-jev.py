#!/usr/bin/env python3
"""Make exactly one synthetic JEV validation call."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
from src.jev_client import JevClient

result = JevClient().analyze(
    {
        "resume": "Synthetic test only. A fictional collaborator built Python APIs and SQL reports.",
        "purpose": "integration validation",
    },
    {
        "python_present": {
            "type": "noul",
            "instructions": "Does the synthetic text explicitly mention Python experience?",
        },
        "technical_depth": {
            "type": "score",
            "instructions": "How strong is the technical evidence?",
            "criteria": ["None", "Initial", "Independent", "Advanced"],
        },
    },
)
print(
    json.dumps(
        {"model": result.model, "answers": result.answers, "usage": result.usage},
        ensure_ascii=False,
    )
)
