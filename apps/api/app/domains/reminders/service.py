"""Reminder generation and inbox state.

Rules (plan §13.7 / §5.3 idea of a persisted inbox):

* ``follow_up_due``   — ``applications.next_follow_up_at`` is set and nearing/past
* ``interview_soon``  — an interview round of the "已面试" detail is scheduled
                        within the next 48h (the round itself lives in stage JSON)
* ``no_reply_stale``  — ``applied`` with no progress for 7 / 14 days
* ``offer_reply_due`` — an offer detail has a reply deadline within 3 days

Generation is idempotent and pull-based: ``GET /workspace/reminders`` syncs the
inbox first, so no worker is required for a single-user local deployment.
Dismissed reminders are never resurrected by a later sync (same ``dedupe_key``).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.domains.applications.constants import TERMINAL_STATUSES
from app.domains.applications.model import Application, ApplicationStageDetail
from app.domains.reminders.model import Reminder, ReminderRule, ReminderStatus
from app.domains.reminders.schemas import (
    ReminderList,
    ReminderRead,
    ReminderSummary,
)

FOLLOW_UP_HORIZON = timedelta(days=7)
FOLLOW_UP_LOOKBACK = timedelta(days=45)
INTERVIEW_HORIZON = timedelta(hours=48)
OFFER_REPLY_LEAD = timedelta(days=3)
STALE_WINDOWS = ((7, "no_reply_stale_7"), (14, "no_reply_stale_14"))
STALE_LOOKBACK = timedelta(days=30)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class ReminderService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # -- inbox ------------------------------------------------------------
    def list(
        self, *, user_id: str, status: ReminderStatus | None, include_snoozed: bool = False
    ) -> ReminderList:
        self.sync(user_id=user_id)
        now = _now()
        statement = select(Reminder).where(Reminder.user_id == user_id)
        if status is not None:
            statement = statement.where(Reminder.status == status)
        else:
            statement = statement.where(Reminder.status == ReminderStatus.pending)
        rows = list(
            self.session.scalars(statement.order_by(Reminder.due_at, Reminder.created_at))
        )
        visible = [
            row
            for row in rows
            if include_snoozed or _aware(row.snoozed_until) is None or _aware(row.snoozed_until) <= now
        ]
        pending = [row for row in visible if row.status == ReminderStatus.pending]
        due_now = [row for row in pending if _aware(row.due_at) <= now]
        return ReminderList(
            items=[ReminderRead.model_validate(row) for row in visible],
            total=len(visible),
            pending=len(pending),
            due_now=len(due_now),
        )

    def summary(self, *, user_id: str) -> ReminderSummary:
        listing = self.list(user_id=user_id, status=None)
        return ReminderSummary(pending=listing.pending, due_now=listing.due_now)

    def mark_done(self, *, user_id: str, reminder_id: str) -> ReminderRead:
        reminder = self._get(user_id=user_id, reminder_id=reminder_id)
        reminder.status = ReminderStatus.done
        reminder.done_at = _now()
        self.session.commit()
        self.session.refresh(reminder)
        return ReminderRead.model_validate(reminder)

    def dismiss(self, *, user_id: str, reminder_id: str) -> ReminderRead:
        reminder = self._get(user_id=user_id, reminder_id=reminder_id)
        reminder.status = ReminderStatus.dismissed
        reminder.done_at = _now()
        self.session.commit()
        self.session.refresh(reminder)
        return ReminderRead.model_validate(reminder)

    def snooze(self, *, user_id: str, reminder_id: str, hours: int) -> ReminderRead:
        reminder = self._get(user_id=user_id, reminder_id=reminder_id)
        if reminder.status != ReminderStatus.pending:
            raise AppError(
                code="REMINDER_NOT_PENDING",
                message="只有待处理的提醒可以稍后提醒",
                status_code=409,
            )
        reminder.snoozed_until = _now() + timedelta(hours=hours)
        self.session.commit()
        self.session.refresh(reminder)
        return ReminderRead.model_validate(reminder)

    # -- generation -------------------------------------------------------
    def sync(self, *, user_id: str) -> None:
        applications = list(
            self.session.scalars(
                select(Application)
                .where(Application.user_id == user_id, Application.deleted_at.is_(None))
                .options(selectinload(Application.stage_details))
            )
        )
        now = _now()
        existing = set(
            self.session.scalars(
                select(Reminder.dedupe_key).where(Reminder.user_id == user_id)
            )
        )
        created = False
        for application in applications:
            if application.status.value in TERMINAL_STATUSES:
                continue
            for spec in self._specs(application, now=now):
                if spec["dedupe_key"] in existing:
                    continue
                self.session.add(
                    Reminder(
                        user_id=user_id,
                        application_id=application.id,
                        rule_type=spec["rule_type"],
                        title=spec["title"],
                        body=spec["body"],
                        due_at=spec["due_at"],
                        dedupe_key=spec["dedupe_key"],
                    )
                )
                existing.add(spec["dedupe_key"])
                created = True
        if created:
            try:
                self.session.commit()
            except IntegrityError:  # pragma: no cover - unique race, next sync retries
                self.session.rollback()

    def close_for_application(self, *, user_id: str, application_id: str) -> None:
        """Terminal application → nothing left to nag about."""

        reminders = list(
            self.session.scalars(
                select(Reminder).where(
                    Reminder.user_id == user_id,
                    Reminder.application_id == application_id,
                    Reminder.status == ReminderStatus.pending,
                )
            )
        )
        for reminder in reminders:
            reminder.status = ReminderStatus.dismissed
            reminder.done_at = _now()

    def _specs(self, application: Application, *, now: datetime) -> list[dict[str, object]]:
        label = f"{application.company_name or '未知公司'} · {application.position_title or '未命名岗位'}"
        specs: list[dict[str, object]] = []

        follow_up = _aware(application.next_follow_up_at)
        if follow_up and now - FOLLOW_UP_LOOKBACK <= follow_up <= now + FOLLOW_UP_HORIZON:
            specs.append(
                {
                    "rule_type": ReminderRule.follow_up_due.value,
                    "title": f"该跟进「{label}」了",
                    "body": "到达你设置的跟进日期，记录一次进展或安排下一次跟进。",
                    "due_at": follow_up,
                    "dedupe_key": self._key("follow_up", application, follow_up),
                }
            )

        for detail in application.stage_details:
            if detail.stage == "interview":
                specs.extend(self._interview_specs(application, detail, label, now))
            elif detail.stage == "offer":
                specs.extend(self._offer_specs(application, detail, label, now))

        applied_at = _aware(application.applied_at)
        if application.status.value == "applied" and applied_at:
            for days, key_prefix in STALE_WINDOWS:
                due_at = applied_at + timedelta(days=days)
                if due_at <= now <= due_at + STALE_LOOKBACK:
                    specs.append(
                        {
                            "rule_type": ReminderRule.no_reply_stale.value,
                            "title": f"「{label}」已 {days} 天没有进展",
                            "body": "可以发一封礼貌的跟进邮件，或判断是否继续等待。",
                            "due_at": due_at,
                            "dedupe_key": self._key(key_prefix, application, due_at),
                        }
                    )
        return specs

    def _interview_specs(
        self,
        application: Application,
        detail: ApplicationStageDetail,
        label: str,
        now: datetime,
    ) -> list[dict[str, object]]:
        payload = detail.payload or {}
        rounds = payload.get("rounds")
        if not isinstance(rounds, list):
            return []
        specs: list[dict[str, object]] = []
        for round_item in rounds:
            if not isinstance(round_item, dict):
                continue
            scheduled_raw = round_item.get("scheduled_at")
            if not isinstance(scheduled_raw, str) or not scheduled_raw:
                continue
            try:
                scheduled = datetime.fromisoformat(scheduled_raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            scheduled = _aware(scheduled)
            if scheduled is None:
                continue
            if not (now <= scheduled <= now + INTERVIEW_HORIZON):
                continue
            index = round_item.get("index")
            specs.append(
                {
                    "rule_type": ReminderRule.interview_soon.value,
                    "title": f"「{label}」有面试安排",
                    "body": f"第 {index} 轮面试将在 {scheduled:%m-%d %H:%M} 开始，记得准备。",
                    "due_at": scheduled - timedelta(hours=24),
                    "dedupe_key": self._key(f"interview_{index}", application, scheduled),
                }
            )
        return specs

    def _offer_specs(
        self,
        application: Application,
        detail: ApplicationStageDetail,
        label: str,
        now: datetime,
    ) -> list[dict[str, object]]:
        payload = detail.payload or {}
        deadline_raw = payload.get("reply_deadline")
        if not isinstance(deadline_raw, str) or not deadline_raw:
            return []
        try:
            deadline = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00"))
        except ValueError:
            return []
        deadline = _aware(deadline)
        if deadline is None:
            return []
        due_at = deadline - OFFER_REPLY_LEAD
        if not (now - timedelta(days=30) <= due_at):
            return []
        return [
            {
                "rule_type": ReminderRule.offer_reply_due.value,
                "title": f"「{label}」的 Offer 答复截止临近",
                "body": f"请在 {deadline:%Y-%m-%d} 前确认是否接受。",
                "due_at": due_at,
                "dedupe_key": self._key("offer_reply", application, deadline),
            }
        ]

    @staticmethod
    def _key(prefix: str, application: Application, stamp: datetime) -> str:
        return f"{prefix}:{application.id}:{stamp.date().isoformat()}"

    def _get(self, *, user_id: str, reminder_id: str) -> Reminder:
        reminder = self.session.scalar(
            select(Reminder).where(
                Reminder.id == reminder_id, Reminder.user_id == user_id
            )
        )
        if reminder is None:
            raise AppError(
                code="REMINDER_NOT_FOUND",
                message="提醒不存在或已删除",
                status_code=404,
                details={"reminder_id": reminder_id},
            )
        return reminder
