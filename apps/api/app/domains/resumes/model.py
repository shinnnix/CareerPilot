from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResumeTemplate(str, Enum):
    classic = "classic"
    modern = "modern"
    elegant = "elegant"
    compact = "compact"


class ResumeSectionKey(str, Enum):
    education = "education"
    experience = "experience"
    project = "project"
    skill = "skill"
    summary = "summary"
    other = "other"


class ResumeSource(str, Enum):
    upload = "upload"
    text = "text"
    manual = "manual"


class OptimizationStatus(str, Enum):
    generated = "generated"
    applied = "applied"
    reverted = "reverted"
    discarded = "discarded"


class ResumeVersionSource(str, Enum):
    """Why a snapshot exists. Only ``locked`` ones back an application."""

    locked = "locked"
    applied_optimization = "applied_optimization"
    manual = "manual"


class Resume(Base):
    """Editable resume workspace derived from a parsed knowledge document.

    The document keeps the immutable normalized text and retrieval chunks; this
    table keeps the structured, user-editable representation that the workspace
    renders and that optimization suggestions are applied to.
    """

    __tablename__ = "resumes"
    __table_args__ = (Index("ix_resumes_user_updated", "user_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    template: Mapped[ResumeTemplate] = mapped_column(
        SqlEnum(ResumeTemplate, native_enum=False),
        nullable=False,
        default=ResumeTemplate.classic,
    )
    font_size: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    head: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    sections: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    target_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Job-catalog target (module 1). Preferred over the legacy ``target_job_id``:
    # announcements are what the 职位信息 page actually imports now.
    target_announcement_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_announcements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source: Mapped[ResumeSource] = mapped_column(
        SqlEnum(ResumeSource, native_enum=False),
        nullable=False,
        default=ResumeSource.text,
    )
    content_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    analysis: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    optimizations: Mapped[list["ResumeOptimization"]] = relationship(
        back_populates="resume",
        cascade="all, delete-orphan",
        order_by="ResumeOptimization.created_at.desc()",
        lazy="selectin",
    )


class ResumeOptimization(Base):
    """One JD-targeted optimization run: report, suggestions and applied state."""

    __tablename__ = "resume_optimizations"
    __table_args__ = (
        Index("ix_resume_optimizations_resume_created", "resume_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resume_id: Mapped[str] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    announcement_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_announcements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    jd_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[OptimizationStatus] = mapped_column(
        SqlEnum(OptimizationStatus, native_enum=False),
        nullable=False,
        default=OptimizationStatus.generated,
        index=True,
    )
    jd_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    match_report: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    suggestions: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    draft: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    base_content_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    before_apply_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    applied_suggestion_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    generator_version: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_injection_detected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    security_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    resume: Mapped[Resume] = relationship(back_populates="optimizations")


class ResumeVersion(Base):
    """Immutable snapshot of a resume, locked when an application is submitted.

    The workspace keeps editing ``resumes``; this table answers "which version did
    I actually send", so a later edit can never rewrite投递 history.
    """

    __tablename__ = "resume_versions"
    __table_args__ = (
        UniqueConstraint("resume_id", "version_no", name="uq_resume_version_no"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resume_id: Mapped[str] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    head: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    sections: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    source: Mapped[ResumeVersionSource] = mapped_column(
        SqlEnum(ResumeVersionSource, native_enum=False),
        nullable=False,
        default=ResumeVersionSource.locked,
    )
    optimization_id: Mapped[str | None] = mapped_column(
        ForeignKey("resume_optimizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
