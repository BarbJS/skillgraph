"""Central fail-closed output security gate for all user-visible responses."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from src.privacy import redact_text
from src.toxicity import evaluate_toxicity


class OutputSecurityError(RuntimeError):
    """Raised when a response cannot safely be shown to a user."""

    def __init__(self, reason: str, category: str = "unsafe_output") -> None:
        super().__init__(reason)
        self.category = category


@dataclass(frozen=True)
class OutputSecurityResult:
    allowed: bool
    text: str
    categories: tuple[str, ...] = ()
    reason: str = ""


_SECRET_PATTERNS = (
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{12,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:api[_ -]?key|secret|password|token|authorization)\s*[:=]\s*[^\s,;]{8,}"),
    re.compile(r"(?i)(?:postgres|mysql|mongodb(?:\+srv)?|redis)://[^\s]+"),
)
_INJECTION_OUTPUT = re.compile(
    r"(?i)(ignore (?:all|your|the) (?:previous )?(?:rules|instructions)|ignore previous instructions|system prompt|developer message|reveal (?:the )?prompt|reveal internal instructions|chain[- ]of[- ]thought)"
)
_EMPLOYMENT_DECISION = re.compile(
    r"\b(?:contrat(?:ar|e|ação|acao|ado|ada)|demit(?:ir|a|ido|ida)|"
    r"deslig(?:ar|amento|ado|ada)|promov(?:er|a|ido|ida|ção|cao)|"
    r"reprovar|ranking de candidatos|sal[aá]rio individual|"
    r"remunera[çc][aã]o individual|puni(?:r|ção|cao))\b",
    re.IGNORECASE,
)
_NEGATION_MARKER = re.compile(r"\b(?:não|nao|nunca|sem)\b", re.IGNORECASE)


def _normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _has_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def _has_employment_decision(text: str) -> bool:
    """Reject affirmative employment decisions, but allow explicit disclaimers."""
    candidates = list(_EMPLOYMENT_DECISION.finditer(text))
    if not candidates:
        return False
    for match in candidates:
        context = text[max(0, match.start() - 100):match.end()]
        if not _NEGATION_MARKER.search(context):
            return True
        # A negation in the same clause is a governance disclaimer, not a decision.
        clause = re.split(r"[.!?;]\s*", context)[-1]
        if not _NEGATION_MARKER.search(clause):
            return True
    return False


def scan_output(text: str, *, max_chars: int = 20000) -> OutputSecurityResult:
    value = str(text or "")
    if not value.strip():
        return OutputSecurityResult(False, "", ("empty_output",), "A resposta final veio vazia.")
    if len(value) > max_chars:
        return OutputSecurityResult(False, "", ("output_limit",), "A resposta final excedeu o limite seguro.")

    redacted, pii_labels = redact_text(value)
    categories: list[str] = []
    if pii_labels:
        categories.append("pii")
    if _has_secret(value):
        categories.append("secret")
    if _INJECTION_OUTPUT.search(_normalized(value)):
        categories.append("prompt_leakage")
    if _has_employment_decision(value):
        categories.append("employment_decision")
    toxicity = evaluate_toxicity(value)
    if not toxicity.passed:
        categories.append("toxicity")

    if categories:
        unique = tuple(dict.fromkeys(categories))
        return OutputSecurityResult(False, "", unique, "Resposta bloqueada por segurança.")
    return OutputSecurityResult(True, redacted, (), "ok")


def validate_user_output(text: str, *, route: str = "") -> str:
    result = scan_output(text)
    if not result.allowed:
        raise OutputSecurityError(result.reason, ",".join(result.categories))
    return result.text
