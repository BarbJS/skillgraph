"""Central privacy and governance sanitization helpers."""

from __future__ import annotations
import re
from typing import Any

_PATTERNS = (
    (
        "cpf",
        re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\bcpf\s*[:=]?\s*\d{11}\b", re.I),
    ),
    ("rg", re.compile(r"\brg\s*[:=]?\s*[\w.-]{5,}\b", re.I)),
    ("email", re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", re.I)),
    (
        "phone",
        re.compile(r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2}\)?[\s-]?)?\d{4,5}[\s-]?\d{4}\b"),
    ),
)
_DECISION_PATTERN = re.compile(
    r"\b(contrat(ar|e)|reprovar|demitir|desligar|promover|ranking de candidatos|sal[aá]rio|remunera[çc][aã]o)\b",
    re.I,
)


def redact_text(value: str) -> tuple[str, list[str]]:
    found: list[str] = []
    result = value
    for label, pattern in _PATTERNS:
        if pattern.search(result):
            found.append(label)
            result = pattern.sub(f"[REDACTED_{label.upper()}]", result)
    return result, found


def sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)[0][:10000]
    if isinstance(value, dict):
        return {
            str(key): sanitize(item)
            for key, item in value.items()
            if str(key).casefold()
            not in {"resume", "resume_text", "prompt", "chain_of_thought", "reasoning"}
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def contains_protected_pii(value: str) -> bool:
    return any(pattern.search(value) for _, pattern in _PATTERNS)


def contains_employment_decision(value: str) -> bool:
    return bool(_DECISION_PATTERN.search(value))


def governance_metadata() -> dict[str, Any]:
    return {
        "decision_type": "development_support",
        "requires_human_review": True,
        "not_for_employment_decisions": True,
    }
