from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


# ---------------------------------------------------------------------------
# Job catalog (module 1): company → announcement → position
# ---------------------------------------------------------------------------


class AnnouncementStatus(str, Enum):
    active = "active"
    archived = "archived"


class AnnouncementVisibility(str, Enum):
    private = "private"
    shared = "shared"


class Company(Base):
    """Company directory. One row per company name across the local catalog."""

    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    company_type: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    company_scale: Mapped[str | None] = mapped_column(String(50), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class AnnouncementSource(Base):
    """Where an announcement came from (WeChat account, company site, manual)."""

    __tablename__ = "announcement_sources"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "name", name="uq_source_owner_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    adapter_key: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    home_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class JobAnnouncement(Base):
    """One recruitment announcement. The table row of the job list page."""

    __tablename__ = "job_announcements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("announcement_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    recruitment_type: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    target_cohort: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    locations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    # Denormalised ``、``-joined copy of ``locations`` so SQLite and Postgres can
    # both filter with a plain LIKE (JSON text is escaped on SQLite).
    locations_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    positions_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    announcement_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_channel: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    deadline_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    apply_method: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[AnnouncementStatus] = mapped_column(
        SqlEnum(AnnouncementStatus, native_enum=False),
        nullable=False,
        default=AnnouncementStatus.active,
        index=True,
    )
    visibility: Mapped[AnnouncementVisibility] = mapped_column(
        SqlEnum(AnnouncementVisibility, native_enum=False),
        nullable=False,
        default=AnnouncementVisibility.private,
    )
    owner_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    company: Mapped[Company] = relationship(lazy="joined")
    source: Mapped[AnnouncementSource | None] = relationship(lazy="joined")
    positions: Mapped[list["JobPosition"]] = relationship(
        back_populates="announcement",
        cascade="all, delete-orphan",
        order_by=lambda: (JobPosition.sort_order, JobPosition.title),
    )


class JobPosition(Base):
    __tablename__ = "job_positions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    announcement_id: Mapped[str] = mapped_column(
        ForeignKey("job_announcements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    city: Mapped[str | None] = mapped_column(String(50), nullable=True)
    education: Mapped[str | None] = mapped_column(String(50), nullable=True)
    headcount: Mapped[str | None] = mapped_column(String(50), nullable=True)
    jd_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    announcement: Mapped[JobAnnouncement] = relationship(back_populates="positions")


class UserJobMark(Base):
    """Per-user mark on an announcement. Currently only ``deferred``."""

    __tablename__ = "user_job_marks"
    __table_args__ = (
        UniqueConstraint("user_id", "announcement_id", name="uq_mark_user_announcement"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    announcement_id: Mapped[str] = mapped_column(
        ForeignKey("job_announcements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="deferred")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class JobImport(Base):
    """Import candidate queue: raw snapshot + parsed draft awaiting confirmation."""

    __tablename__ = "job_imports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="parsed_rule", index=True)
    parsed: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    raw_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_used: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class UserTablePreference(Base):
    __tablename__ = "user_table_preferences"
    __table_args__ = (UniqueConstraint("user_id", "table_key", name="uq_table_pref"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    table_key: Mapped[str] = mapped_column(String(50), nullable=False)
    visible_columns: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

