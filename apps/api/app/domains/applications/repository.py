from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.domains.applications.constants import (
    STATUS_FILTER_ALIASES,
    TERMINAL_STATUSES,
)
from app.domains.applications.model import (
    Application,
    ApplicationEvent,
    ApplicationStageDetail,
    ApplicationStatus,
    GeneratedArtifact,
    MatchFeedback,
)
from app.domains.applications.schemas import ApplicationListQuery
from app.domains.jobs.model import Job


@dataclass(frozen=True)
class ApplicationRow:
    application: Application
    job: Job | None


def _status_members(values: frozenset[str] | set[str]) -> list[ApplicationStatus]:
    known = ApplicationStatus._value2member_map_
    return [known[value] for value in values if value in known]


class ApplicationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # -- reads -------------------------------------------------------------
    def _base_statement(self) -> Select[tuple[Application, Job]]:
        return select(Application, Job).outerjoin(Job, Job.id == Application.job_id)

    def _conditions(self, *, user_id: str, query: ApplicationListQuery) -> list[object]:
        conditions: list[object] = [
            Application.user_id == user_id,
            Application.deleted_at.is_(None),
        ]
        keyword = (query.keyword or "").strip()
        if keyword:
            like = f"%{keyword}%"
            # Legacy rows keep the company/title on the old ``jobs`` row, so the
            # search has to look through the coalesced snapshot (plan §3.7-2).
            company = func.coalesce(Application.company_name, Job.company_name)
            title = func.coalesce(Application.position_title, Job.title)
            conditions.append(
                or_(
                    company.ilike(like),
                    title.ilike(like),
                    Application.contact_name.ilike(like),
                    Application.notes.ilike(like),
                )
            )
        if query.status:
            members = _status_members(STATUS_FILTER_ALIASES.get(query.status, {query.status}))
            conditions.append(Application.status.in_(members))
        return conditions

    def _order(self, sort: str) -> list[object]:
        if sort == "updated_desc":
            return [Application.updated_at.desc(), Application.id]
        if sort == "follow_up_asc":
            return [
                case((Application.next_follow_up_at.is_(None), 1), else_=0),
                Application.next_follow_up_at.asc(),
                Application.updated_at.desc(),
            ]
        # ``applied_desc`` falls back to the creation date for rows without a
        # submission date (plan §3.1).
        return [
            func.coalesce(Application.applied_at, Application.created_at).desc(),
            Application.id,
        ]

    def search(
        self, *, user_id: str, query: ApplicationListQuery
    ) -> tuple[list[ApplicationRow], int]:
        conditions = self._conditions(user_id=user_id, query=query)
        total = int(
            self.session.scalar(
                select(func.count())
                .select_from(Application)
                .outerjoin(Job, Job.id == Application.job_id)
                .where(*conditions)
            )
            or 0
        )
        statement = (
            self._base_statement()
            .where(*conditions)
            .order_by(*self._order(query.sort))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
        rows = [ApplicationRow(*row) for row in self.session.execute(statement)]
        return rows, total

    def list(
        self,
        *,
        user_id: str,
        status: ApplicationStatus | None = None,
        limit: int | None = None,
    ) -> list[ApplicationRow]:
        statement = (
            self._base_statement()
            .where(Application.user_id == user_id, Application.deleted_at.is_(None))
            .order_by(
                func.coalesce(Application.applied_at, Application.created_at).desc(),
                Application.id,
            )
        )
        if status:
            statement = statement.where(Application.status == status)
        if limit:
            statement = statement.limit(limit)
        return [ApplicationRow(*row) for row in self.session.execute(statement)]

    def status_counts(self, *, user_id: str) -> dict[str, int]:
        statement = (
            select(Application.status, func.count())
            .where(Application.user_id == user_id, Application.deleted_at.is_(None))
            .group_by(Application.status)
        )
        counts: dict[str, int] = {}
        for status, count in self.session.execute(statement):
            value = status.value if isinstance(status, ApplicationStatus) else str(status)
            counts[value] = counts.get(value, 0) + int(count)
        return counts

    def get(
        self,
        *,
        user_id: str,
        application_id: str,
        with_events: bool = False,
        for_update: bool = False,
        include_deleted: bool = False,
    ) -> ApplicationRow | None:
        statement = self._base_statement().where(
            Application.id == application_id, Application.user_id == user_id
        )
        if not include_deleted:
            statement = statement.where(Application.deleted_at.is_(None))
        if with_events:
            statement = statement.options(
                selectinload(Application.events),
                selectinload(Application.stage_details),
            )
            # The service appends events/stage details directly to the session, so
            # an identity-mapped instance can hold a stale collection. Force a
            # refresh whenever the caller asks for the aggregate.
            statement = statement.execution_options(populate_existing=True)
        if for_update:
            statement = statement.with_for_update()
        row = self.session.execute(statement).first()
        return ApplicationRow(*row) if row else None

    def get_by_job(self, *, user_id: str, job_id: str) -> Application | None:
        return self.session.scalar(
            select(Application).where(
                Application.user_id == user_id,
                Application.job_id == job_id,
                Application.deleted_at.is_(None),
            )
        )

    def get_by_position(self, *, user_id: str, position_id: str) -> Application | None:
        return self.session.scalar(
            select(Application).where(
                Application.user_id == user_id,
                Application.position_id == position_id,
                Application.deleted_at.is_(None),
            )
        )

    def count(self, *, user_id: str) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(Application)
                .where(Application.user_id == user_id, Application.deleted_at.is_(None))
            )
            or 0
        )

    def list_followups(self, *, user_id: str, before: datetime) -> list[ApplicationRow]:
        statement = (
            self._base_statement()
            .where(
                Application.user_id == user_id,
                Application.deleted_at.is_(None),
                Application.next_follow_up_at.is_not(None),
                Application.next_follow_up_at <= before,
                Application.status.not_in(
                    _status_members(TERMINAL_STATUSES) or [ApplicationStatus.withdrawn]
                ),
            )
            .order_by(Application.next_follow_up_at.asc(), Application.updated_at.desc())
        )
        return [ApplicationRow(*row) for row in self.session.execute(statement)]

    # -- writes ------------------------------------------------------------
    def add(self, application: Application) -> None:
        self.session.add(application)
        self.session.flush()

    def add_event(self, event: ApplicationEvent) -> None:
        self.session.add(event)
        self.session.flush()

    def get_feedback(self, *, user_id: str, job_id: str) -> MatchFeedback | None:
        return self.session.scalar(
            select(MatchFeedback).where(
                MatchFeedback.user_id == user_id, MatchFeedback.job_id == job_id
            )
        )

    def add_artifact(self, artifact: GeneratedArtifact) -> None:
        self.session.add(artifact)
        self.session.flush()

    # -- stage details -----------------------------------------------------
    def stage_details(self, *, application_id: str) -> list[ApplicationStageDetail]:
        return list(
            self.session.scalars(
                select(ApplicationStageDetail)
                .where(ApplicationStageDetail.application_id == application_id)
                .order_by(ApplicationStageDetail.created_at)
            )
        )

    def get_stage_detail(
        self, *, application_id: str, stage: str
    ) -> ApplicationStageDetail | None:
        return self.session.scalar(
            select(ApplicationStageDetail).where(
                ApplicationStageDetail.application_id == application_id,
                ApplicationStageDetail.stage == stage,
            )
        )

    def save_stage_detail(self, detail: ApplicationStageDetail) -> ApplicationStageDetail:
        self.session.add(detail)
        self.session.flush()
        return detail

    def delete_stage_detail(self, detail: ApplicationStageDetail) -> None:
        self.session.delete(detail)
        self.session.flush()
