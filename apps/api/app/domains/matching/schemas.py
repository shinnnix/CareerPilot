from pydantic import BaseModel, Field

from app.domains.retrieval.schemas import SearchHit


class MatchRequest(BaseModel):
    resume_document_id: str


class HardGateResult(BaseModel):
    passed: bool
    checks: dict[str, bool]
    reasons: list[str]
    unknowns: list[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    required_skill_coverage: float = Field(ge=0, le=1)
    preferred_skill_coverage: float = Field(ge=0, le=1)
    experience_semantic_score: float = Field(ge=0, le=1)
    project_domain_score: float = Field(ge=0, le=1)
    preference_score: float = Field(ge=0, le=1)
    freshness_score: float = Field(ge=0, le=1)


class MatchReport(BaseModel):
    job_id: str
    resume_document_id: str
    eligible: bool
    total_score: float = Field(ge=0, le=100)
    hard_gate: HardGateResult
    breakdown: ScoreBreakdown
    matched_required_skills: list[str]
    missing_required_skills: list[str]
    matched_preferred_skills: list[str]
    missing_preferred_skills: list[str]
    evidence: list[SearchHit]
    scoring_version: str
