from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.reminders.model import ReminderStatus


class ReminderRead(BaseModel):
    id: str
    application_id: str | None
    rule_type: str
    title: str
    body: str | None
    due_at: datetime
    status: ReminderStatus
    snoozed_until: datetime | None
    done_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReminderList(BaseModel):
    items: list[ReminderRead]
    total: int
    pending: int
    due_now: int


class ReminderSnooze(BaseModel):
    hours: int = Field(default=24, ge=1, le=24 * 14)


class ReminderSummary(BaseModel):
    pending: int
    due_now: int
