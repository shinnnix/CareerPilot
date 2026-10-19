from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

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
