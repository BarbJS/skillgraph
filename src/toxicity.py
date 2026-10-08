"""Toxicity safety gate for generated responses."""

from __future__ import annotations
import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ToxicityResult:
    score: float
    passed: bool
    reason: str
    mode: str


_BLOCKED = re.compile(
    r"\b(vai se f|idiota|burro|incompetente|lixo|odeio você|vou te matar|matar você)\b",
    re.I,
)
_SAFE_RESPONSE = "Posso ajudar com competências, trilhas, treinamentos e políticas de desenvolvimento de forma respeitosa."


def evaluate_toxicity(text: str, *, model=None) -> ToxicityResult:
    if _BLOCKED.search(text):
        return ToxicityResult(
            0.0,
            False,
            "A resposta contém linguagem potencialmente agressiva ou ameaçadora.",
            "deterministic",
        )
    if (
        os.getenv("TOXICITY_LIVE_ENABLED", "false").casefold() == "true"
        and model is not None
    ):
        try:
            from deepeval.metrics import ToxicityMetric
            from deepeval.test_case import LLMTestCase

            metric = ToxicityMetric(
                threshold=float(os.getenv("TOXICITY_THRESHOLD", "0.9")),
                model=model,
                include_reason=True,
                async_mode=False,
            )
            case = LLMTestCase(input="SkillGraph response safety", actual_output=text)
            metric.measure(case)
            score = float(metric.score or 0.0)
            return ToxicityResult(
                score,
                bool(metric.is_successful()),
                str(metric.reason or ""),
                "deepeval",
            )
        except Exception:
            pass
    return ToxicityResult(
        1.0, True, "Nenhuma expressão bloqueada foi identificada.", "deterministic"
    )


def safe_response(text: str, *, model=None) -> tuple[str, ToxicityResult]:
    result = evaluate_toxicity(text, model=model)
    return (text if result.passed else _SAFE_RESPONSE), result
