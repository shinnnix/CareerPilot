from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.domains.applications.model import (
    Application,
    ApplicationEvent,
    ApplicationStatus,
    GeneratedArtifact,
    MatchFeedback,
)
from app.domains.jobs.model import Job


@dataclass(frozen=True)
class ApplicationRow:
    application: Application
    job: Job


class ApplicationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, *, user_id: str, status: ApplicationStatus | None) -> list[ApplicationRow]:
        statement = (
            select(Application, Job)
            .join(Job, Job.id == Application.job_id)
            .where(Application.user_id == user_id)
            .order_by(Application.updated_at.desc(), Application.id)
        )
        if status:
            statement = statement.where(Application.status == status)
        return [ApplicationRow(*row) for row in self.session.execute(statement)]

    def get(
        self,
        *,
        user_id: str,
        application_id: str,
        with_events: bool = False,
        for_update: bool = False,
    ) -> ApplicationRow | None:
        statement = (
            select(Application, Job)
            .join(Job, Job.id == Application.job_id)
            .where(Application.id == application_id, Application.user_id == user_id)
        )
        if with_events:
            statement = statement.options(selectinload(Application.events))
        if for_update:
            statement = statement.with_for_update()
        row = self.session.execute(statement).first()
        return ApplicationRow(*row) if row else None

    def get_by_job(self, *, user_id: str, job_id: str) -> Application | None:
        return self.session.scalar(
            select(Application).where(Application.user_id == user_id, Application.job_id == job_id)
        )

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

    def count(self, *, user_id: str) -> int:
        return int(
            self.session.scalar(
                select(func.count()).select_from(Application).where(Application.user_id == user_id)
            )
            or 0
        )

    def list_followups(self, *, user_id: str, before: datetime) -> list[ApplicationRow]:
        statement = (
            select(Application, Job)
            .join(Job, Job.id == Application.job_id)
            .where(
                Application.user_id == user_id,
                Application.next_follow_up_at.is_not(None),
                Application.next_follow_up_at <= before,
                Application.status.not_in({ApplicationStatus.rejected, ApplicationStatus.withdrawn}),
            )
            .order_by(Application.next_follow_up_at.asc(), Application.updated_at.desc())
        )
        return [ApplicationRow(*row) for row in self.session.execute(statement)]
