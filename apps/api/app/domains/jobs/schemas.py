from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.domains.jobs.constants import (
    COMPANY_TYPES,
    DEFAULT_VISIBLE_COLUMNS,
    RECRUITMENT_TYPES,
    TABLE_COLUMNS,
)
from app.domains.jobs.model import EmploymentType, JobStatus, RemoteType


class JobFields(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    company_name: str = Field(min_length=1, max_length=100)
    city: str | None = Field(default=None, max_length=50)
    employment_type: EmploymentType = EmploymentType.internship
    remote_type: RemoteType = RemoteType.onsite
    salary_min: Decimal | None = Field(default=None, ge=0)
    salary_max: Decimal | None = Field(default=None, ge=0)
    internship_days_per_week: int | None = Field(default=None, ge=1, le=7)
    internship_months: int | None = Field(default=None, ge=1, le=36)
    required_skills: list[str] = Field(default_factory=list, max_length=50)
    preferred_skills: list[str] = Field(default_factory=list, max_length=50)
    source_url: HttpUrl | None = None
    raw_text: str = Field(min_length=20, max_length=50_000)
    status: JobStatus = JobStatus.active

    @model_validator(mode="after")
    def validate_salary_range(self) -> "JobFields":
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min must not be greater than salary_max")
        return self


class JobCreate(JobFields):
    pass


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=100)
    company_name: str | None = Field(default=None, min_length=1, max_length=100)
    city: str | None = Field(default=None, max_length=50)
    employment_type: EmploymentType | None = None
    remote_type: RemoteType | None = None
    salary_min: Decimal | None = Field(default=None, ge=0)
    salary_max: Decimal | None = Field(default=None, ge=0)
    internship_days_per_week: int | None = Field(default=None, ge=1, le=7)
    internship_months: int | None = Field(default=None, ge=1, le=36)
    required_skills: list[str] | None = Field(default=None, max_length=50)
    preferred_skills: list[str] | None = Field(default=None, max_length=50)
    source_url: HttpUrl | None = None
    raw_text: str | None = Field(default=None, min_length=20, max_length=50_000)
    status: JobStatus | None = None

    @model_validator(mode="after")
    def reject_null_for_required_fields(self) -> "JobUpdate":
        required_fields = {
            "title",
            "company_name",
            "employment_type",
            "remote_type",
            "raw_text",
            "status",
        }
        null_fields = [
            field
            for field in required_fields & self.model_fields_set
            if getattr(self, field) is None
        ]
        if null_fields:
            raise ValueError(f"Fields cannot be null: {', '.join(sorted(null_fields))}")
        return self


class JobRead(JobFields):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobList(BaseModel):
    items: list[JobRead]
    page: int
    page_size: int
    total: int


# ---------------------------------------------------------------------------
# Job catalog (module 1)
# ---------------------------------------------------------------------------


class JobCatalogQuery(BaseModel):
    """Normalised filter set for the catalog list (all fields optional)."""

    keyword: str | None = None
    company: str | None = None
    status: str | None = None
    company_type: str | None = None
    recruitment_type: str | None = None
    target_cohort: str | None = None
    location: str | None = None
    job_category: str | None = None
    sort: Literal["updated_desc", "published_desc", "deadline_asc"] = "updated_desc"
    page: int = 1
    page_size: int = 20


class JobRowCompany(BaseModel):
    name: str
    type: str | None = None
    scale: str | None = None
    industry: str | None = None


class DeadlineInfo(BaseModel):
    text: str | None = None
    at: date | None = None


class JobSourceInfo(BaseModel):
    kind: str
    name: str | None = None
    url: str | None = None


class JobRow(BaseModel):
    id: str
    title: str
    company: JobRowCompany
    recruitment_type: str | None = None
    target_cohort: str | None = None
    locations: list[str] = Field(default_factory=list)
    positions_preview: str
    position_count: int
    published_at: date | None = None
    updated_at: datetime
    deadline: DeadlineInfo
    mark_status: str
    mark_status_label: str
    mark_note: str | None = None
    stage_summary: dict[str, int] = Field(default_factory=dict)
    application_ids: list[str] = Field(default_factory=list)
    applied_position_count: int = 0
    source: JobSourceInfo


class JobCatalogList(BaseModel):
    items: list[JobRow]
    page: int
    page_size: int
    total: int
    page_count: int


class JobPositionRead(BaseModel):
    id: str
    title: str
    category: str | None = None
    city: str | None = None
    education: str | None = None
    headcount: str | None = None
    jd_text: str | None = None
    sort_order: int = 0
    application_id: str | None = None
    application_status: str | None = None
    application_status_label: str | None = None

    model_config = ConfigDict(from_attributes=True)


class JobAnnouncementDetail(BaseModel):
    id: str
    title: str
    company: JobRowCompany
    recruitment_type: str | None = None
    target_cohort: str | None = None
    locations: list[str] = Field(default_factory=list)
    positions_text: str | None = None
    announcement_url: str | None = None
    source_url: str | None = None
    source_channel: str
    published_at: datetime | None = None
    deadline: DeadlineInfo
    raw_text: str
    apply_method: dict[str, object] = Field(default_factory=dict)
    snapshot_at: datetime | None = None
    status: str
    visibility: str
    mark_status: str
    mark_status_label: str
    mark_note: str | None = None
    positions: list[JobPositionRead] = Field(default_factory=list)
    source: JobSourceInfo
    created_at: datetime
    updated_at: datetime


class JobMarkUpdate(BaseModel):
    status: Literal["deferred", "none"] = "deferred"
    note: str | None = Field(default=None, max_length=500)


class JobMarkBatch(BaseModel):
    announcement_ids: list[str] = Field(min_length=1, max_length=100)
    status: Literal["deferred", "none"] = "deferred"
    note: str | None = Field(default=None, max_length=500)


class JobMarkRead(BaseModel):
    announcement_id: str
    mark_status: str
    mark_status_label: str
    note: str | None = None


class FacetOption(BaseModel):
    value: str
    label: str
    count: int


class JobFacets(BaseModel):
    company_types: list[FacetOption]
    recruitment_types: list[FacetOption]
    target_cohorts: list[FacetOption]
    locations: list[FacetOption]
    job_categories: list[FacetOption]
    statuses: list[FacetOption]


class JobImportDraft(BaseModel):
    title: str | None = None
    company_name: str | None = None
    recruitment_type: str | None = None
    target_cohort: str | None = None
    locations: list[str] = Field(default_factory=list)
    positions: list[str] = Field(default_factory=list)
    deadline_text: str | None = None
    deadline_at: datetime | None = None
    published_at: datetime | None = None
    apply_method: dict[str, object] = Field(default_factory=dict)
    confidence: dict[str, str] = Field(default_factory=dict)
    # Rule vs LLM disagreements (plan §2.7.1). The rule value always wins; the
    # confirmation screen shows both so a human can pick.
    needs_review: bool = False
    alternatives: dict[str, dict[str, object]] = Field(default_factory=dict)


class JobImportRead(BaseModel):
    id: str
    mode: str
    source_url: str | None = None
    status: str
    llm_used: bool = False
    error: str | None = None
    parsed: JobImportDraft
    raw_snapshot: str = ""
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobImportList(BaseModel):
    items: list[JobImportRead]
    total: int


class JobImportTextRequest(BaseModel):
    raw_text: str = Field(min_length=20, max_length=200_000)
    source_name: str | None = Field(default=None, max_length=200)
    source_url: HttpUrl | None = None


class JobImportArticleRequest(BaseModel):
    url: HttpUrl
    source_name: str | None = Field(default=None, max_length=200)


class JobPositionInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=50)
    city: str | None = Field(default=None, max_length=50)
    education: str | None = Field(default=None, max_length=50)
    headcount: str | None = Field(default=None, max_length=50)
    jd_text: str | None = Field(default=None, max_length=20_000)


class JobImportConfirm(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    company_name: str = Field(min_length=1, max_length=200)
    company_type: str | None = None
    company_scale: str | None = Field(default=None, max_length=50)
    industry: str | None = Field(default=None, max_length=100)
    recruitment_type: str | None = None
    target_cohort: str | None = Field(default=None, max_length=20)
    locations: list[str] = Field(default_factory=list, max_length=20)
    positions: list[JobPositionInput] = Field(default_factory=list, max_length=100)
    deadline_text: str | None = Field(default=None, max_length=100)
    deadline_at: date | None = None
    published_at: date | None = None
    announcement_url: HttpUrl | None = None
    apply_method: dict[str, object] = Field(default_factory=dict)
    raw_text: str | None = Field(default=None, max_length=200_000)

    @model_validator(mode="after")
    def validate_enums(self) -> "JobImportConfirm":
        if self.company_type and self.company_type not in COMPANY_TYPES:
            raise ValueError(f"company_type must be one of {COMPANY_TYPES}")
        if self.recruitment_type and self.recruitment_type not in RECRUITMENT_TYPES:
            raise ValueError(f"recruitment_type must be one of {RECRUITMENT_TYPES}")
        return self


class ColumnOption(BaseModel):
    key: str
    label: str
    default: bool


class JobTablePreference(BaseModel):
    table_key: str
    visible_columns: list[str]
    available_columns: list[ColumnOption]


class JobTablePreferenceUpdate(BaseModel):
    visible_columns: list[str] = Field(min_length=1, max_length=len(TABLE_COLUMNS))

    @model_validator(mode="after")
    def validate_columns(self) -> "JobTablePreferenceUpdate":
        unknown = [column for column in self.visible_columns if column not in TABLE_COLUMNS]
        if unknown:
            raise ValueError(f"unknown columns: {', '.join(unknown)}")
        if len(set(self.visible_columns)) != len(self.visible_columns):
            raise ValueError("duplicate columns are not allowed")
        return self


DEFAULT_COLUMN_KEYS = tuple(DEFAULT_VISIBLE_COLUMNS)

