"""Macro guardrails shared by the Core, runtime and tool boundaries."""

from __future__ import annotations

import re
from typing import Any


class AgentGuardrailError(RuntimeError):
    pass


_PII = re.compile(
    r"\bcpf\b|\brg\b|\bcnpj\b|e-?mail pessoal|telefone pessoal|endereço pessoal", re.I
)
_INJECTION = re.compile(
    r"ignore (as|suas) regras|revele (o|seu|suas) prompt|mostre (as|suas) instruções",
    re.I,
)
_DECISION = re.compile(r"contrat(e|ar)|demit|deslig|promov|salário|remunera", re.I)
_SECRET = re.compile(r"(?i)bearer\s+\S+|sk-[A-Za-z0-9_-]{12,}|AIza[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{12,}|api[_ -]?key\s*[:=]\s*\S+|password\s*[:=]\s*\S+")
_OUTPUT_INJECTION = re.compile(r"(?i)ignore (?:all|your|the) (?:previous )?(?:rules|instructions)|system prompt|developer message|chain[- ]of[- ]thought")


def validate_agent_input(text: str, *, max_chars: int = 4000) -> None:
    if len(text) > max_chars:
        raise AgentGuardrailError("A mensagem excede o limite permitido.")
    if _PII.search(text):
        raise AgentGuardrailError(
            "Remova dados pessoais identificáveis antes de continuar."
        )
    if _INJECTION.search(text):
        raise AgentGuardrailError("A solicitação tenta alterar as regras do sistema.")


def validate_agent_output(value: Any) -> Any:
    if value is None:
        raise AgentGuardrailError("O agente não retornou resultado.")
    text = str(value)
    if _PII.search(text) or _DECISION.search(text) or _SECRET.search(text) or _OUTPUT_INJECTION.search(text):
        raise AgentGuardrailError(
            "A resposta contém conteúdo fora do escopo permitido."
        )
    return value


def tool_allowed(agent: str, tool_name: str) -> bool:
    permissions = {
        "Core Router": set(),
        "Resume Interpreter": {"JevResumeExtractionTool"},
        "Profile Normalizer": set(),
        "Prediction Specialist": {"CompetencyRecommendationTool"},
        "Gap Analyst": set(),
        "Learning Path & Training Recommendation Agent": {"TrainingCatalogTool"},
        "Structured Data Specialist": {"CompetencyGapTool"},
        "Policy Specialist": {"DifyPolicyTool"},
        "Safety Reviewer": set(),
        "Response Synthesizer": set(),
    }
    return tool_name in permissions.get(agent, set())
