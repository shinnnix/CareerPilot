"""Reminder inbox endpoints (follow-ups, interviews, offer deadlines)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user_id, get_reminder_service
from app.core.errors import ErrorResponse
from app.domains.reminders.model import ReminderStatus
from app.domains.reminders.schemas import (
    ReminderList,
    ReminderRead,
    ReminderSnooze,
    ReminderSummary,
)
from app.domains.reminders.service import ReminderService

router = APIRouter(prefix="/workspace/reminders", tags=["reminders"])

ERRORS = {
    404: {"model": ErrorResponse, "description": "Reminder not found"},
    409: {"model": ErrorResponse, "description": "Reminder state conflict"},
}


@router.get("", response_model=ReminderList)
def list_reminders(
    service: Annotated[ReminderService, Depends(get_reminder_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    reminder_status: Annotated[ReminderStatus | None, Query(alias="status")] = None,
    include_snoozed: Annotated[bool, Query()] = False,
) -> ReminderList:
    return service.list(
        user_id=user_id, status=reminder_status, include_snoozed=include_snoozed
    )


@router.get("/summary", response_model=ReminderSummary)
def reminder_summary(
    service: Annotated[ReminderService, Depends(get_reminder_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ReminderSummary:
    return service.summary(user_id=user_id)


@router.post("/{reminder_id}/done", response_model=ReminderRead, responses=ERRORS)
def complete_reminder(
    reminder_id: str,
    service: Annotated[ReminderService, Depends(get_reminder_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ReminderRead:
    return service.mark_done(user_id=user_id, reminder_id=reminder_id)


@router.post("/{reminder_id}/dismiss", response_model=ReminderRead, responses=ERRORS)
def dismiss_reminder(
    reminder_id: str,
    service: Annotated[ReminderService, Depends(get_reminder_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ReminderRead:
    return service.dismiss(user_id=user_id, reminder_id=reminder_id)


@router.post("/{reminder_id}/snooze", response_model=ReminderRead, responses=ERRORS)
def snooze_reminder(
    reminder_id: str,
    payload: ReminderSnooze,
    service: Annotated[ReminderService, Depends(get_reminder_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ReminderRead:
    return service.snooze(user_id=user_id, reminder_id=reminder_id, hours=payload.hours)
