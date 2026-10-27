from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domains.applications.constants import (
    CLOSED_REASONS,
    FILTERABLE_STATUSES,
    REJECTED_STAGES,
    STAGE_LABELS,
)
from app.domains.applications.model import ApplicationStatus, ArtifactType
from app.domains.resumes.schemas import ResumeVersionRead


class ApplicationCreate(BaseModel):
    job_id: str
    status: ApplicationStatus = ApplicationStatus.not_applied
    notes: str | None = Field(default=None, max_length=5000)
    next_follow_up_at: datetime | None = None


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = Field(default=None, max_length=5000)
    next_follow_up_at: datetime | None = None
    interview_feedback: str | None = Field(default=None, max_length=10000)
    event_note: str | None = Field(default=None, max_length=1000)


class ApplicationRead(BaseModel):
    id: str
    job_id: str | None = None
    announcement_id: str | None = None
    position_id: str | None = None
    job_title: str
    company_name: str
    status: ApplicationStatus
    notes: str | None
    next_follow_up_at: datetime | None
    interview_feedback: str | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApplicationList(BaseModel):
    items: list[ApplicationRead]
    total: int


class ApplicationMetrics(BaseModel):
    total: int
    by_status: dict[str, int]
    due_follow_ups: int


class ApplicationEventRead(BaseModel):
    id: str
    event_type: str
    from_status: str | None
    to_status: str | None
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationDetail(ApplicationRead):
    events: list[ApplicationEventRead]


class FeedbackUpsert(BaseModel):
    relevant: bool
    reason: str | None = Field(default=None, max_length=2000)


class FeedbackRead(BaseModel):
    job_id: str
    relevant: bool
    reason: str | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Citation(BaseModel):
    source_type: str
    source_id: str
    quote: str


class ArtifactItem(BaseModel):
    text: str
    citations: list[Citation]


class ArtifactRead(BaseModel):
    id: str
    job_id: str
    resume_document_id: str
    artifact_type: ArtifactType
    content: list[ArtifactItem]
    citations: list[Citation]
    citation_valid: bool
    generator_version: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PersonalizationRequest(BaseModel):
    resume_document_id: str


class PersonalizationResult(BaseModel):
    resume_bullets: ArtifactRead
    skill_gap_plan: ArtifactRead


class AutofillField(BaseModel):
    field_id: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=300)
    field_type: Literal["text", "email", "tel", "url", "textarea", "select", "file", "checkbox"] = "text"
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=100)


class AutofillRequest(BaseModel):
    resume_document_id: str
    fields: list[AutofillField] = Field(min_length=1, max_length=200)
    # Optional browser-local profile (plan §5.1). Used for this mapping only and
    # never persisted server-side.
    profile: dict[str, Any] | None = None


class AutofillFieldPlan(BaseModel):
    field_id: str
    label: str
    value: str | None
    confidence: float = Field(ge=0, le=1)
    status: Literal["ready", "review", "unsupported"]
    source_type: Literal["profile", "resume", "job", "none"]
    source_id: str | None = None
    evidence: str | None = None
    reason: str | None = None


class AutofillPlan(BaseModel):
    run_id: str
    application_id: str
    job_id: str
    resume_document_id: str
    fields: list[AutofillFieldPlan]
    ready_count: int
    review_count: int
    generated_at: datetime


# ---------------------------------------------------------------------------
# Module 2 — application records workspace surface (plan §3.5 / §3.6)
# ---------------------------------------------------------------------------

ApplicationSort = Literal["applied_desc", "updated_desc", "follow_up_asc"]
StageKey = Literal["written_test", "interview", "offer"]
StageResult = Literal["passed", "failed", "unknown"]


class ApplicationListQuery(BaseModel):
    """Filters mirrored into the URL query string by the list page."""

    keyword: str | None = Field(default=None, max_length=200)
    status: str | None = Field(default=None, max_length=30)
    sort: ApplicationSort = "applied_desc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("status")
    @classmethod
    def _known_status(cls, value: str | None) -> str | None:
        if value and value not in FILTERABLE_STATUSES:
            raise ValueError(f"未知状态：{value}")
        return value


class ApplicationRow(BaseModel):
    id: str
    company_name: str
    position_title: str
    status: str
    status_label: str
    is_terminal: bool
    applied_at: datetime | None
    follow_up_at: datetime | None
    follow_up_due: bool
    channel: str | None
    contact_name: str | None
    contact_info: str | None
    link: str | None
    notes: str | None
    closed_reason: str | None
    rejected_stage: str | None
    announcement_id: str | None
    position_id: str | None
    job_id: str | None
    resume_id: str | None = None
    resume_version_id: str | None = None
    row_version: int
    created_at: datetime
    updated_at: datetime


class ApplicationListResult(BaseModel):
    items: list[ApplicationRow]
    page: int
    page_size: int
    total: int
    page_count: int
    status_counts: dict[str, int]


class ApplicationCreatedResult(BaseModel):
    items: list[ApplicationRow]
    total: int


class ApplicationMetricsResult(BaseModel):
    total: int
    by_status: dict[str, int]
    due_follow_ups: int
    terminal: int
    active: int


class ApplicationStageDetailRead(BaseModel):
    id: str
    stage: StageKey
    stage_label: str
    payload: dict[str, Any]
    occurred_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApplicationDetailResult(ApplicationRow):
    events: list[ApplicationEventRead]
    stage_details: list[ApplicationStageDetailRead]
    allowed_transitions: list[str]
    recommended_missing: list[str]
    resume_version: ResumeVersionRead | None = None


class ApplicationCreateRequest(BaseModel):
    """One payload for both entry points: catalog positions or a manual row.

    ``position_ids`` switches to batch mode and then ``announcement_id`` is
    required; otherwise ``company_name`` + ``position_title`` are required.
    """

    announcement_id: str | None = None
    position_ids: list[str] = Field(default_factory=list, max_length=50)
    company_name: str | None = Field(default=None, max_length=200)
    position_title: str | None = Field(default=None, max_length=200)
    status: ApplicationStatus = ApplicationStatus.applied
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None
    channel: str | None = Field(default=None, max_length=50)
    contact_name: str | None = Field(default=None, max_length=100)
    contact_info: str | None = Field(default=None, max_length=200)
    link: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=5000)
    # Manual rows are not deduplicated by the database, so the client can
    # confirm "same company + position + date" and retry with this flag (§3.3).
    allow_duplicate: bool = False

    @model_validator(mode="after")
    def _check_shape(self) -> "ApplicationCreateRequest":
        self.position_ids = list(dict.fromkeys(self.position_ids))
        if self.position_ids:
            if not self.announcement_id:
                raise ValueError("按岗位创建投递时必须提供 announcement_id")
            return self
        if not (self.company_name or "").strip():
            raise ValueError("公司名称不能为空")
        if not (self.position_title or "").strip():
            raise ValueError("岗位名称不能为空")
        if self.applied_at and self.follow_up_at and self.follow_up_at < self.applied_at:
            raise ValueError("跟进日期不能早于投递日期")
        return self


class ApplicationUpdateRequest(BaseModel):
    """``row_version`` drives optimistic locking (plan §3.2)."""

    status: ApplicationStatus | None = None
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None
    channel: str | None = Field(default=None, max_length=50)
    contact_name: str | None = Field(default=None, max_length=100)
    contact_info: str | None = Field(default=None, max_length=200)
    link: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=5000)
    closed_reason: str | None = Field(default=None, max_length=50)
    rejected_stage: str | None = Field(default=None, max_length=50)
    event_note: str | None = Field(default=None, max_length=1000)
    row_version: int = Field(ge=1)

    @field_validator("closed_reason")
    @classmethod
    def _known_closed_reason(cls, value: str | None) -> str | None:
        if value and value not in CLOSED_REASONS:
            raise ValueError(f"未知的已挂原因：{value}")
        return value

    @field_validator("rejected_stage")
    @classmethod
    def _known_rejected_stage(cls, value: str | None) -> str | None:
        if value and value not in REJECTED_STAGES:
            raise ValueError(f"未知的挂点环节：{value}")
        return value

    @model_validator(mode="after")
    def _check_dates(self) -> "ApplicationUpdateRequest":
        if self.applied_at and self.follow_up_at and self.follow_up_at < self.applied_at:
            raise ValueError("跟进日期不能早于投递日期")
        return self


class WrittenTestPayload(BaseModel):
    taken_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=0, le=1440)
    link: str | None = Field(default=None, max_length=1000)
    score: str | None = Field(default=None, max_length=50)
    result: StageResult = "unknown"
    notes: str | None = Field(default=None, max_length=5000)


class InterviewRound(BaseModel):
    index: int = Field(default=1, ge=1, le=15)
    scheduled_at: datetime | None = None
    completed_at: datetime | None = None
    format: Literal["online", "onsite", "phone"] | None = None
    interviewer: str | None = Field(default=None, max_length=200)
    questions: list[str] = Field(default_factory=list, max_length=50)
    notes: str | None = Field(default=None, max_length=2000)
    self_rating: int | None = Field(default=None, ge=1, le=5)

    @field_validator("questions")
    @classmethod
    def _question_length(cls, value: list[str]) -> list[str]:
        for question in value:
            if len(question) > 500:
                raise ValueError("单条面试问题不能超过 500 字")
        return value


class InterviewPayload(BaseModel):
    rounds: list[InterviewRound] = Field(default_factory=list, max_length=15)
    summary: str | None = Field(default=None, max_length=5000)
    result: StageResult = "unknown"


class SalaryPayload(BaseModel):
    monthly: float | None = Field(default=None, ge=0, le=10_000_000)
    annual: float | None = Field(default=None, ge=0, le=10_000_000)
    bonus: float | None = Field(default=None, ge=0, le=10_000_000)


class OfferPayload(BaseModel):
    base_city: str | None = Field(default=None, max_length=50)
    salary: SalaryPayload | None = None
    start_date: date | None = None
    reply_deadline: date | None = None
    benefits: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=5000)


STAGE_PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "written_test": WrittenTestPayload,
    "interview": InterviewPayload,
    "offer": OfferPayload,
}


class StageDetailUpsert(BaseModel):
    """Details are optional back-fill: never blocks a status change (§3.4.1)."""

    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None


def stage_label(stage: str) -> str:
    return STAGE_LABELS.get(stage, stage)
