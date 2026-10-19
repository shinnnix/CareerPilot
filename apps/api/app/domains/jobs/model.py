from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Integer, Numeric, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EmploymentType(str, Enum):
    internship = "internship"
    full_time = "full_time"
    part_time = "part_time"


class RemoteType(str, Enum):
    onsite = "onsite"
    hybrid = "hybrid"
    remote = "remote"


class JobStatus(str, Enum):
    active = "active"
    archived = "archived"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    city: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    employment_type: Mapped[EmploymentType] = mapped_column(
        SqlEnum(EmploymentType, native_enum=False),
        nullable=False,
        default=EmploymentType.internship,
    )
    remote_type: Mapped[RemoteType] = mapped_column(
        SqlEnum(RemoteType, native_enum=False),
        nullable=False,
        default=RemoteType.onsite,
    )
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    internship_days_per_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    internship_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    preferred_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        SqlEnum(JobStatus, native_enum=False),
        nullable=False,
        default=JobStatus.active,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
