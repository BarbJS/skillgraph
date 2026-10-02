"""Validated JSON contracts exchanged by SkillGraph agents."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SkillEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    normalized_name: str | None = None
    level: float | None = Field(default=None, ge=0, le=5)
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: str | None = None


class EmployeeProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_context: str = "colaborador não identificado"
    skills: list[SkillEvidence] = Field(default_factory=list)
    source: Literal["manual", "uploaded_resume", "mock"] = "manual"
    contains_pii: bool = False
    missing_information: list[str] = Field(default_factory=list)


class TrackRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track: str
    compatibility: float = Field(ge=0, le=1)


class PredictionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommendations: list[TrackRecommendation] = Field(default_factory=list)
    recognized_skills: list[dict[str, Any]] = Field(default_factory=list)
    unrecognized_skills: list[dict[str, Any]] = Field(default_factory=list)
    priorities: list[dict[str, Any]] = Field(default_factory=list)
    uncertainty: dict[str, Any] = Field(default_factory=dict)
    local_explanations: list[dict[str, Any]] = Field(default_factory=list)


class TrainingRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    competency: str | None = None
    duration_hours: float | None = None
    modality: str | None = None
    prerequisite: str | None = None


class PolicyEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    sources: list[dict[str, str]] = Field(default_factory=list)
    supported: bool = True


class ReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: bool
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_human_review: bool = True


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = ""
    employee_context: str | None = None
    profile: EmployeeProfile | None = None
    resume_text: str | None = None


class FinalAgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    profile: EmployeeProfile | None = None
    prediction: PredictionResult | None = None
    trainings: list[TrainingRecommendation] = Field(default_factory=list)
    policy: PolicyEvidence | None = None
    review: ReviewResult | None = None
    requires_human_review: bool = True
