"""Input guardrails and simulated roles for the local SkillGraph MVP."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum


class UserRole(StrEnum):
    DESENVOLVEDOR = "desenvolvedor"
    GESTOR = "gestor"
    RH = "RH"


@dataclass(frozen=True)
class SecurityDecision:
    allowed: bool
    reason: str
    category: str = "allowed"

    @property
    def public_message(self) -> str:
        if self.allowed:
            return ""
        return "Não posso fornecer essas informações devido às restrições de segurança."


_SENSITIVE_PATTERNS = (
    ("pii", r"\bcpf\b|\brg\b|\bcnpj\b|e-?mail pessoal|telefone pessoal|endereço pessoal"),
    ("individual_compensation", r"sal[aá]rio individual|remunera[çc][aã]o de f\d{4}"),
    ("prompt_injection", r"ignore (as|suas) regras|revele (o|seu|suas) prompt|mostre (as|suas) instru[çc][õo]es"),
    ("unsafe_sql", r"\b(select|insert|update|delete|drop|alter)\b(?:\s+\w+){0,4}"),
)


def evaluate_input(question: str, role: UserRole = UserRole.DESENVOLVEDOR) -> SecurityDecision:
    """Apply domain guardrails before any model or database call."""

    normalized = " ".join(question.lower().split())
    for category, pattern in _SENSITIVE_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            return SecurityDecision(False, f"blocked:{category}", category)
    if role not in set(UserRole):
        return SecurityDecision(False, "blocked:unknown_role", "unknown_role")
    return SecurityDecision(True, "allowed")


def safe_question_fingerprint(question: str) -> str:
    """Return a non-reversible identifier suitable for local metrics."""

    return hashlib.sha256(question.strip().encode("utf-8")).hexdigest()[:16]
