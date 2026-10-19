from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApplicationStatus(str, Enum):
    saved = "saved"
    preparing = "preparing"
    applied = "applied"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"
    withdrawn = "withdrawn"


class AutofillRun(Base):
    __tablename__ = "autofill_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_document_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fields: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    ready_count: Mapped[int] = mapped_column(Integer, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ArtifactType(str, Enum):
    resume_bullets = "resume_bullets"
    skill_gap_plan = "skill_gap_plan"


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_application_user_job"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        SqlEnum(ApplicationStatus, native_enum=False),
        nullable=False,
        default=ApplicationStatus.saved,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    interview_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by=lambda: (ApplicationEvent.created_at, ApplicationEvent.id),
    )


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    application: Mapped[Application] = relationship(back_populates="events")


class MatchFeedback(Base):
    __tablename__ = "match_feedback"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_feedback_user_job"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relevant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class GeneratedArtifact(Base):
    __tablename__ = "generated_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_document_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Migration 0004 intentionally stores this small, stable value set as VARCHAR.
    # Pydantic converts it back to ArtifactType at the API boundary.
    artifact_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    content: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    citations: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    citation_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    generator_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
