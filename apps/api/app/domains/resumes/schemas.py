from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domains.matching.schemas import HardGateResult, ScoreBreakdown
from app.domains.resumes.model import (
    OptimizationStatus,
    ResumeSectionKey,
    ResumeSource,
    ResumeTemplate,
    ResumeVersionSource,
)

MAX_BULLET_CHARS = 600
MAX_BULLETS_PER_ENTRY = 20
MAX_ENTRIES_PER_SECTION = 30
MAX_SECTIONS = 24


def _check_bullets(bullets: list[str]) -> list[str]:
    cleaned = [bullet.strip() for bullet in bullets]
    for bullet in cleaned:
        if len(bullet) > MAX_BULLET_CHARS:
            raise ValueError(f"bullet must be at most {MAX_BULLET_CHARS} characters")
    return cleaned


class ResumeLink(BaseModel):
    label: str = Field(min_length=1, max_length=40)
    url: str = Field(min_length=3, max_length=500)


class ResumeHead(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    target_title: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=320)
    city: str | None = Field(default=None, max_length=100)
    links: list[ResumeLink] = Field(default_factory=list, max_length=10)


class ResumeEntry(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(default="", max_length=300)
    subtitle: str | None = Field(default=None, max_length=300)
    period: str | None = Field(default=None, max_length=100)
    bullets: list[str] = Field(default_factory=list, max_length=MAX_BULLETS_PER_ENTRY)

    @field_validator("bullets")
    @classmethod
    def validate_bullets(cls, value: list[str]) -> list[str]:
        return _check_bullets(value)


class ResumeSection(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    key: ResumeSectionKey
    title: str = Field(min_length=1, max_length=50)
    entries: list[ResumeEntry] = Field(
        default_factory=list, max_length=MAX_ENTRIES_PER_SECTION
    )


class ResumeAnalysis(BaseModel):
    parser_version: str | None = None
    source_document_id: str | None = None
    detected_section_titles: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    source_content_hash: str | None = None


class ResumeImportText(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    raw_text: str = Field(min_length=20, max_length=200_000)
    template: ResumeTemplate = ResumeTemplate.classic
    target_job_id: str | None = None
    target_announcement_id: str | None = None


class ResumeFromDocument(BaseModel):
    document_id: str = Field(min_length=1, max_length=36)
    title: str | None = Field(default=None, max_length=200)
    template: ResumeTemplate = ResumeTemplate.classic
    target_job_id: str | None = None
    target_announcement_id: str | None = None


class ResumeManualCreate(BaseModel):
    title: str = Field(default="我的简历", min_length=1, max_length=200)
    template: ResumeTemplate = ResumeTemplate.classic
    target_job_id: str | None = None
    target_announcement_id: str | None = None
    head: ResumeHead | None = None


class ResumeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    template: ResumeTemplate | None = None
    font_size: int | None = Field(default=None, ge=10, le=22)
    target_job_id: str | None = None
    target_announcement_id: str | None = None
    head: ResumeHead | None = None
    sections: list[ResumeSection] | None = Field(default=None, max_length=MAX_SECTIONS)

    @model_validator(mode="after")
    def reject_null_for_non_nullable_fields(self) -> "ResumeUpdate":
        for field in ("title", "template", "font_size", "head", "sections"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"Field cannot be null: {field}")
        return self


class ResumeSummary(BaseModel):
    id: str
    title: str
    template: ResumeTemplate
    font_size: int
    target_job_id: str | None
    target_announcement_id: str | None = None
    source: ResumeSource
    content_version: int
    document_id: str | None
    candidate_name: str | None
    target_title: str | None
    section_count: int
    entry_count: int
    created_at: datetime
    updated_at: datetime


class ResumeDetail(ResumeSummary):
    head: ResumeHead
    sections: list[ResumeSection]
    analysis: ResumeAnalysis
    optimization_count: int = 0


class ResumeList(BaseModel):
    items: list[ResumeSummary]
    page: int
    page_size: int
    total: int


class JdSnapshot(BaseModel):
    source: Literal["job", "document", "text", "announcement"]
    job_id: str | None = None
    announcement_id: str | None = None
    document_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    company_name: str | None = None
    city: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    internship_days_per_week: int | None = None
    internship_months: int | None = None
    raw_text_excerpt: str = ""


class ResumeOptimizeRequest(BaseModel):
    job_id: str | None = Field(default=None, max_length=36)
    announcement_id: str | None = Field(default=None, max_length=36)
    jd_document_id: str | None = Field(default=None, max_length=36)
    jd_text: str | None = Field(default=None, min_length=20, max_length=20_000)
    focus: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def require_single_jd_source(self) -> "ResumeOptimizeRequest":
        provided = [
            name
            for name, value in (
                ("job_id", self.job_id),
                ("announcement_id", self.announcement_id),
                ("jd_document_id", self.jd_document_id),
                ("jd_text", self.jd_text),
            )
            if value
        ]
        if len(provided) != 1:
            raise ValueError(
                "必须且只能提供 job_id、announcement_id、jd_document_id 或 jd_text 之一"
            )
        if self.jd_text is not None:
            self.jd_text = self.jd_text.strip()
        if self.focus is not None:
            self.focus = self.focus.strip() or None
        return self


class ResumeCitation(BaseModel):
    source_type: Literal[
        "resume_entry",
        "resume_section",
        "resume_head",
        "job",
        "announcement",
        "jd_document",
        "jd_text",
    ]
    source_id: str
    quote: str = Field(min_length=1, max_length=400)


ResumeSuggestionKind = Literal[
    "rewrite_bullet",
    "add_bullet",
    "add_skill",
    "add_section",
    "gap_plan",
]


class ResumeSuggestion(BaseModel):
    id: str
    kind: ResumeSuggestionKind
    section_id: str
    entry_id: str | None = None
    bullet_index: int | None = Field(default=None, ge=0, le=MAX_BULLETS_PER_ENTRY)
    title: str
    original: str | None = None
    proposed: str | None = None
    rationale: str
    keywords: list[str] = Field(default_factory=list)
    citations: list[ResumeCitation]
    priority: Literal["high", "medium", "low"] = "medium"
    confidence: float = Field(default=0.6, ge=0, le=1)
    requires_new_fact: bool = False
    applicable: bool = True


class ResumeMatchEvidence(BaseModel):
    section_id: str
    section_title: str
    entry_id: str | None = None
    text: str


class ResumeMatchReport(BaseModel):
    source: Literal["job", "document", "text", "announcement"]
    job_id: str | None = None
    jd_document_id: str | None = None
    jd_title: str
    company_name: str | None = None
    city: str | None = None
    eligible: bool
    total_score: float = Field(ge=0, le=100)
    breakdown: ScoreBreakdown
    hard_gate: HardGateResult
    matched_required_skills: list[str]
    missing_required_skills: list[str]
    matched_preferred_skills: list[str]
    missing_preferred_skills: list[str]
    keyword_hits: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    evidence: list[ResumeMatchEvidence] = Field(default_factory=list)
    scoring_version: str


class ResumeDraft(BaseModel):
    head: ResumeHead
    sections: list[ResumeSection]
    applied_suggestion_ids: list[str] = Field(default_factory=list)


class ResumeOptimizationSummary(BaseModel):
    id: str
    resume_id: str
    status: OptimizationStatus
    job_id: str | None
    announcement_id: str | None = None
    jd_document_id: str | None
    jd_title: str
    total_score: float
    suggestion_count: int
    applicable_count: int
    created_at: datetime
    applied_at: datetime | None


class ResumeOptimizationRead(ResumeOptimizationSummary):
    jd: JdSnapshot
    match_report: ResumeMatchReport
    suggestions: list[ResumeSuggestion]
    draft: ResumeDraft
    requires_review_count: int
    base_content_version: int
    applied_suggestion_ids: list[str]
    generator_version: str
    prompt_injection_detected: bool
    security_flags: list[str]

    model_config = ConfigDict(from_attributes=True)


class ResumeOptimizationList(BaseModel):
    items: list[ResumeOptimizationSummary]
    total: int


class ResumeApplyRequest(BaseModel):
    suggestion_ids: list[str] = Field(default_factory=list, max_length=100)


class ResumeApplyResult(BaseModel):
    resume: ResumeDetail
    optimization: ResumeOptimizationRead
    applied_suggestion_ids: list[str]


class ResumeVersionRead(BaseModel):
    id: str
    resume_id: str
    version_no: int
    source: ResumeVersionSource
    note: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResumeVersionDetail(ResumeVersionRead):
    head: ResumeHead
    sections: list[ResumeSection]


class ResumeVersionList(BaseModel):
    items: list[ResumeVersionRead]
    total: int


class ResumeVersionLockRequest(BaseModel):
    """``resume_id`` is optional: without it the server picks the best match."""

    resume_id: str | None = Field(default=None, max_length=36)
    note: str | None = Field(default=None, max_length=200)
