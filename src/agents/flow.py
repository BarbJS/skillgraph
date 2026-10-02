"""Deterministic, framework-neutral agent flow state.

CrewAI can wrap these stages later; keeping state and contracts here makes the
system testable without external model/API calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.agents.schemas import EmployeeProfile, FinalAgentResponse, PredictionResult, ReviewResult, TrainingRecommendation


@dataclass
class AgentFlowState:
    message: str = ""
    employee_profile: EmployeeProfile | None = None
    prediction: PredictionResult | None = None
    trainings: list[TrainingRecommendation] = field(default_factory=list)
    policy: dict[str, Any] | None = None
    review: ReviewResult | None = None
    answer: str = ""

    def as_context(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "employee_profile": self.employee_profile.model_dump() if self.employee_profile else None,
            "prediction": self.prediction.model_dump() if self.prediction else None,
            "trainings": [item.model_dump() for item in self.trainings],
            "policy": self.policy,
            "review": self.review.model_dump() if self.review else None,
        }

    def final_response(self) -> FinalAgentResponse:
        return FinalAgentResponse(
            answer=self.answer,
            profile=self.employee_profile,
            prediction=self.prediction,
            trainings=self.trainings,
            policy=self.policy,
            review=self.review,
            requires_human_review=True,
        )
