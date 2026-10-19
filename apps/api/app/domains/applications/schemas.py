from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domains.applications.model import ApplicationStatus, ArtifactType


class ApplicationCreate(BaseModel):
    job_id: str
    status: ApplicationStatus = ApplicationStatus.saved
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
    job_id: str
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


class AutofillFieldPlan(BaseModel):
    field_id: str
    label: str
    value: str | None
    confidence: float = Field(ge=0, le=1)
    status: Literal["ready", "review", "unsupported"]
    source_type: Literal["resume", "job", "none"]
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
