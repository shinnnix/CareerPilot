"""In-app reminders for follow-ups, interviews and offer deadlines."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReminderStatus(str, Enum):
    pending = "pending"
    done = "done"
    dismissed = "dismissed"


class ReminderRule(str, Enum):
    follow_up_due = "follow_up_due"
    interview_soon = "interview_soon"
    no_reply_stale = "no_reply_stale"
    offer_reply_due = "offer_reply_due"


class Reminder(Base):
    """One actionable inbox item.

    Reminders are generated from application state by ``ReminderService.sync``
    (idempotent, keyed by ``dedupe_key``) instead of being recomputed on every
    page load, so "done / dismiss / snooze" survive refreshes.
    """

    __tablename__ = "reminders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    application_id: Mapped[str | None] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=True, index=True
    )
    rule_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[ReminderStatus] = mapped_column(
        SqlEnum(ReminderStatus, native_enum=False),
        nullable=False,
        default=ReminderStatus.pending,
        index=True,
    )
    snoozed_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="inbox")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
