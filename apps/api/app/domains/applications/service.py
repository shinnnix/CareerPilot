from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from math import ceil

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, DocumentNotFoundError, JobNotFoundError
from app.domains.applications.constants import (
    APPLIED_STATUSES,
    CORRECTABLE_STATUSES,
    STAGE_LABELS,
    TERMINAL_STATUSES,
    can_transition,
    is_terminal,
    next_statuses,
    status_label,
)
from app.domains.applications.model import (
    Application,
    ApplicationEvent,
    ApplicationStageDetail,
    ApplicationStatus,
    ArtifactType,
    AutofillRun,
    GeneratedArtifact,
    MatchFeedback,
)
from app.domains.applications.repository import ApplicationRepository, ApplicationRow
from app.domains.applications.schemas import (
    STAGE_PAYLOAD_MODELS,
    ApplicationCreate,
    ApplicationCreateRequest,
    ApplicationDetail,
    ApplicationDetailResult,
    ApplicationEventRead,
    ApplicationList,
    ApplicationListQuery,
    ApplicationListResult,
    ApplicationMetrics,
    ApplicationMetricsResult,
    ApplicationRead,
    ApplicationStageDetailRead,
    ApplicationUpdate,
    ApplicationUpdateRequest,
    ArtifactItem,
    ArtifactRead,
    AutofillFieldPlan,
    AutofillPlan,
    AutofillRequest,
    Citation,
    FeedbackRead,
    FeedbackUpsert,
    PersonalizationResult,
    StageDetailUpsert,
)
from app.domains.applications.schemas import (
    ApplicationRow as ApplicationRowSchema,
)
from app.domains.documents.model import DocumentType
from app.domains.documents.repository import DocumentRepository
from app.domains.jobs.model import JobAnnouncement, JobPosition
from app.domains.jobs.repository import JobRepository
from app.domains.matching.service import MatchingService
from app.domains.matching.skills import normalize_skills
from app.domains.reminders.service import ReminderService
from app.domains.resumes.model import ResumeVersionSource
from app.domains.resumes.service import ResumeVersionService

GENERATOR_VERSION = "evidence-template-v1"
AUTOFILL_VERSION = "autofill-rules-v1"

# Which detail fields the UI nudges for, per stage (plan §3.4.1). Purely
# advisory: an empty list means the stage detail looks complete enough.
RECOMMENDED_FIELDS = {
    "written_test": ("taken_at", "result"),
    "interview": ("rounds", "summary"),
    "offer": ("base_city", "start_date", "reply_deadline"),
}


class ApplicationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ApplicationRepository(session)
        self.jobs = JobRepository(session)

    def create(self, *, user_id: str, payload: ApplicationCreate) -> ApplicationRead:
        job = self.jobs.get(user_id=user_id, job_id=payload.job_id)
        if job is None:
            raise JobNotFoundError(payload.job_id)
        existing = self.repository.get_by_job(user_id=user_id, job_id=payload.job_id)
        if existing:
            raise AppError(
                code="APPLICATION_EXISTS",
                message="该职位已经在申请看板中",
                status_code=409,
                details={"application_id": existing.id},
            )
        application = Application(
            user_id=user_id,
            job_id=payload.job_id,
            # Snapshot the company/position so the row still renders after the
            # legacy ``jobs`` row is removed (plan §3.3 denormalisation).
            company_name=job.company_name,
            position_title=job.title,
            status=payload.status,
            notes=payload.notes,
            next_follow_up_at=payload.next_follow_up_at,
            applied_at=(
                datetime.now(timezone.utc)
                if payload.status.value in APPLIED_STATUSES
                else None
            ),
        )
        try:
            self.repository.add(application)
            self.repository.add_event(
                ApplicationEvent(
                    application_id=application.id,
                    user_id=user_id,
                    event_type="created",
                    from_status=None,
                    to_status=application.status.value,
                    note=payload.notes,
                )
            )
            self.session.commit()
            self.session.refresh(application)
        except IntegrityError:
            self.session.rollback()
            existing = self.repository.get_by_job(user_id=user_id, job_id=payload.job_id)
            raise AppError(
                code="APPLICATION_EXISTS",
                message="该职位已经在申请看板中",
                status_code=409,
                details={"application_id": existing.id if existing else None},
            ) from None
        return self._read(ApplicationRow(application, job))

    def list(self, *, user_id: str, status: ApplicationStatus | None) -> ApplicationList:
        rows = self.repository.list(user_id=user_id, status=status)
        return ApplicationList(items=[self._read(row) for row in rows], total=len(rows))

    def followups(self, *, user_id: str, before: datetime) -> ApplicationList:
        rows = self.repository.list_followups(user_id=user_id, before=before)
        return ApplicationList(items=[self._read(row) for row in rows], total=len(rows))

    def metrics(self, *, user_id: str) -> ApplicationMetrics:
        rows = self.repository.list(user_id=user_id, status=None)
        counts = {status.value: 0 for status in ApplicationStatus}
        for row in rows:
            counts[row.application.status.value] += 1
        now = datetime.now(timezone.utc)
        due = len(self.repository.list_followups(user_id=user_id, before=now))
        return ApplicationMetrics(total=len(rows), by_status=counts, due_follow_ups=due)

    def get(self, *, user_id: str, application_id: str) -> ApplicationDetail:
        row = self._get(user_id=user_id, application_id=application_id, with_events=True)
        return ApplicationDetail(
            **self._read(row).model_dump(),
            events=row.application.events,
        )

    def update(
        self, *, user_id: str, application_id: str, payload: ApplicationUpdate
    ) -> ApplicationDetail:
        row = self._get(
            user_id=user_id,
            application_id=application_id,
            with_events=True,
            for_update=True,
        )
        application = row.application
        old_status = application.status
        if payload.status and payload.status != old_status:
            if not can_transition(old_status.value, payload.status.value):
                raise AppError(
                    code="INVALID_APPLICATION_TRANSITION",
                    message=(
                        f"投递状态不能从 {status_label(old_status.value)} "
                        f"变为 {status_label(payload.status.value)}"
                    ),
                    status_code=409,
                    details={
                        "from_status": old_status.value,
                        "to_status": payload.status.value,
                        "allowed": next_statuses(old_status.value),
                    },
                )
            application.status = payload.status
            if payload.status.value in APPLIED_STATUSES and application.applied_at is None:
                application.applied_at = datetime.now(timezone.utc)
            if is_terminal(payload.status.value):
                # Reaching a terminal status closes the follow-up reminder.
                application.next_follow_up_at = None
            self.repository.add_event(
                ApplicationEvent(
                    application_id=application.id,
                    user_id=user_id,
                    event_type="status_changed",
                    from_status=old_status.value,
                    to_status=payload.status.value,
                    note=payload.event_note,
                )
            )
        elif payload.event_note:
            self.repository.add_event(
                ApplicationEvent(
                    application_id=application.id,
                    user_id=user_id,
                    event_type="note_added",
                    from_status=old_status.value,
                    to_status=old_status.value,
                    note=payload.event_note,
                )
            )
        if "notes" in payload.model_fields_set:
            application.notes = payload.notes
        if "next_follow_up_at" in payload.model_fields_set:
            application.next_follow_up_at = payload.next_follow_up_at
        if "interview_feedback" in payload.model_fields_set:
            application.interview_feedback = payload.interview_feedback
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.expire(application, ["events"])
        return self.get(user_id=user_id, application_id=application_id)

    def upsert_feedback(
        self, *, user_id: str, job_id: str, payload: FeedbackUpsert
    ) -> FeedbackRead:
        if self.jobs.get(user_id=user_id, job_id=job_id) is None:
            raise JobNotFoundError(job_id)
        feedback = self.repository.get_feedback(user_id=user_id, job_id=job_id)
        if feedback is None:
            feedback = MatchFeedback(user_id=user_id, job_id=job_id, **payload.model_dump())
            self.session.add(feedback)
        else:
            feedback.relevant = payload.relevant
            feedback.reason = payload.reason
        try:
            self.session.commit()
            self.session.refresh(feedback)
        except Exception:
            self.session.rollback()
            raise
        return FeedbackRead.model_validate(feedback)

    def _get(
        self,
        *,
        user_id: str,
        application_id: str,
        with_events: bool,
        for_update: bool = False,
    ) -> ApplicationRow:
        row = self.repository.get(
            user_id=user_id,
            application_id=application_id,
            with_events=with_events,
            for_update=for_update,
        )
        if row is None:
            raise AppError(
                code="APPLICATION_NOT_FOUND",
                message="申请记录不存在或无权访问",
                status_code=404,
                details={"application_id": application_id},
            )
        return row

    @staticmethod
    def _read(row: ApplicationRow) -> ApplicationRead:
        application = row.application
        return ApplicationRead(
            id=application.id,
            job_id=application.job_id,
            announcement_id=application.announcement_id,
            position_id=application.position_id,
            job_title=application.position_title
            or (row.job.title if row.job else "未命名岗位"),
            company_name=application.company_name
            or (row.job.company_name if row.job else "未知公司"),
            status=application.status,
            notes=application.notes,
            next_follow_up_at=application.next_follow_up_at,
            interview_feedback=application.interview_feedback,
            applied_at=application.applied_at,
            created_at=application.created_at,
            updated_at=application.updated_at,
        )


class WorkspaceApplicationService:
    """Application records surface for module 2 (plan §3.1 – §3.6)."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ApplicationRepository(session)

    # -- reads -------------------------------------------------------------
    def list(self, *, user_id: str, query: ApplicationListQuery) -> ApplicationListResult:
        rows, total = self.repository.search(user_id=user_id, query=query)
        return ApplicationListResult(
            items=[self._row(row) for row in rows],
            page=query.page,
            page_size=query.page_size,
            total=total,
            page_count=max(1, ceil(total / query.page_size)) if total else 1,
            status_counts=self.repository.status_counts(user_id=user_id),
        )

    def followups(self, *, user_id: str, before: datetime) -> ApplicationListResult:
        rows = self.repository.list_followups(user_id=user_id, before=before)
        return ApplicationListResult(
            items=[self._row(row) for row in rows],
            page=1,
            page_size=max(len(rows), 1),
            total=len(rows),
            page_count=1,
            status_counts=self.repository.status_counts(user_id=user_id),
        )

    def detail(self, *, user_id: str, application_id: str) -> ApplicationDetailResult:
        row = self._get(user_id=user_id, application_id=application_id)
        application = row.application
        details = self._sorted_details(application.stage_details)
        version = ResumeVersionService(self.session).version_read(
            user_id=user_id, version_id=application.resume_version_id
        )
        return ApplicationDetailResult(
            **self._row(row).model_dump(),
            events=[ApplicationEventRead.model_validate(event) for event in application.events],
            stage_details=[self._stage_read(detail) for detail in details],
            allowed_transitions=next_statuses(application.status.value),
            recommended_missing=self._recommended_missing(application, details),
            resume_version=version,
        )

    def lock_resume_version(
        self, *, user_id: str, application_id: str, resume_id: str | None, note: str | None
    ) -> ApplicationDetailResult:
        """Snapshot a resume for this application (explicit user choice allowed)."""

        row = self._get(user_id=user_id, application_id=application_id)
        application = row.application
        versions = ResumeVersionService(self.session)
        if resume_id:
            resume = versions._get_resume(user_id=user_id, resume_id=resume_id)
            version = versions.lock(
                user_id=user_id,
                resume=resume,
                source=ResumeVersionSource.locked,
                note=note or "手动锁定",
            )
            application.resume_id = resume.id
            application.resume_version_id = version.id
        else:
            version = versions.lock_for_application(user_id=user_id, application=application)
            if version is None:
                raise AppError(
                    code="RESUME_REQUIRED",
                    message="还没有可锁定的简历，请先在「我的简历」导入一份",
                    status_code=409,
                )
        application.row_version = (application.row_version or 1) + 1
        self.repository.add_event(
            ApplicationEvent(
                application_id=application.id,
                user_id=user_id,
                event_type="resume_version_locked",
                from_status=application.status.value,
                to_status=application.status.value,
                note=note or f"锁定简历版本 v{version.version_no}",
            )
        )
        self._commit()
        return self.detail(user_id=user_id, application_id=application_id)

    def metrics(self, *, user_id: str) -> ApplicationMetricsResult:
        counts = {status.value: 0 for status in ApplicationStatus}
        counts.update(self.repository.status_counts(user_id=user_id))
        total = sum(counts.values())
        terminal = sum(counts.get(value, 0) for value in TERMINAL_STATUSES)
        due = len(self.repository.list_followups(user_id=user_id, before=_now()))
        return ApplicationMetricsResult(
            total=total,
            by_status=counts,
            due_follow_ups=due,
            terminal=terminal,
            active=total - terminal,
        )

    def export_csv(self, *, user_id: str, query: ApplicationListQuery) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "公司",
                "岗位",
                "状态",
                "投递日期",
                "跟进日期",
                "渠道",
                "联系人",
                "联系方式",
                "已挂原因",
                "挂点环节",
                "链接",
                "备注",
            ]
        )
        page = 1
        while True:
            paged = query.model_copy(update={"page": page, "page_size": 100})
            rows, total = self.repository.search(user_id=user_id, query=paged)
            for row in rows:
                item = self._row(row)
                writer.writerow(
                    [
                        item.company_name,
                        item.position_title,
                        item.status_label,
                        _date_text(item.applied_at),
                        _date_text(item.follow_up_at),
                        item.channel or "",
                        item.contact_name or "",
                        item.contact_info or "",
                        item.closed_reason or "",
                        item.rejected_stage or "",
                        item.link or "",
                        (item.notes or "").replace("\r\n", " ").replace("\n", " "),
                    ]
                )
            if page * 100 >= total or not rows:
                break
            page += 1
        return "\ufeff" + buffer.getvalue()

    # -- writes ------------------------------------------------------------
    def create(
        self, *, user_id: str, payload: ApplicationCreateRequest
    ) -> list[ApplicationRowSchema]:
        if payload.position_ids:
            created = self._create_from_positions(user_id=user_id, payload=payload)
        else:
            created = [self._create_manual(user_id=user_id, payload=payload)]
        return [self._row(ApplicationRow(application, None)) for application in created]

    def update(
        self, *, user_id: str, application_id: str, payload: ApplicationUpdateRequest
    ) -> ApplicationDetailResult:
        row = self._get(user_id=user_id, application_id=application_id)
        application = row.application
        current_version = application.row_version or 1
        if payload.row_version != current_version:
            raise AppError(
                code="APPLICATION_VERSION_CONFLICT",
                message="这条投递已在别处更新，请刷新后再修改",
                status_code=409,
                details={"current_row_version": current_version},
            )

        old_status = application.status
        new_status = payload.status
        if new_status is not None and new_status != old_status:
            if not can_transition(old_status.value, new_status.value):
                raise AppError(
                    code="INVALID_APPLICATION_TRANSITION",
                    message=(
                        f"投递状态不能从 {status_label(old_status.value)} "
                        f"变为 {status_label(new_status.value)}"
                    ),
                    status_code=409,
                    details={
                        "from_status": old_status.value,
                        "to_status": new_status.value,
                        "allowed": next_statuses(old_status.value),
                    },
                )
            application.status = new_status
            if new_status.value in APPLIED_STATUSES and application.applied_at is None:
                application.applied_at = payload.applied_at or _now()
            if is_terminal(new_status.value):
                application.next_follow_up_at = None
                # Terminal application → nothing left to nag about.
                ReminderService(self.session).close_for_application(
                    user_id=user_id, application_id=application.id
                )
            elif new_status.value == "applied" and application.resume_version_id is None:
                # Lock the resume that was sent, so later edits can't rewrite history.
                ResumeVersionService(self.session).lock_for_application(
                    user_id=user_id, application=application
                )
            corrected = old_status.value in CORRECTABLE_STATUSES
            self.repository.add_event(
                ApplicationEvent(
                    application_id=application.id,
                    user_id=user_id,
                    event_type="status_corrected" if corrected else "status_changed",
                    from_status=old_status.value,
                    to_status=new_status.value,
                    note=payload.event_note,
                )
            )
        elif payload.event_note:
            self.repository.add_event(
                ApplicationEvent(
                    application_id=application.id,
                    user_id=user_id,
                    event_type="note_added",
                    from_status=old_status.value,
                    to_status=old_status.value,
                    note=payload.event_note,
                )
            )

        self._apply_fields(application, payload)
        application.row_version = current_version + 1
        self._commit()
        return self.detail(user_id=user_id, application_id=application_id)

    def delete(self, *, user_id: str, application_id: str) -> None:
        row = self._get(user_id=user_id, application_id=application_id)
        application = row.application
        application.deleted_at = _now()
        application.row_version = (application.row_version or 1) + 1
        self.repository.add_event(
            ApplicationEvent(
                application_id=application.id,
                user_id=user_id,
                event_type="deleted",
                from_status=application.status.value,
                to_status=None,
                note=None,
            )
        )
        self._commit()

    # -- stage details -----------------------------------------------------
    def stage_details(self, *, user_id: str, application_id: str) -> list[ApplicationStageDetailRead]:
        row = self._get(user_id=user_id, application_id=application_id)
        return [self._stage_read(detail) for detail in self._sorted_details(row.application.stage_details)]

    def upsert_stage_detail(
        self,
        *,
        user_id: str,
        application_id: str,
        stage: str,
        payload: StageDetailUpsert,
    ) -> ApplicationStageDetailRead:
        model = STAGE_PAYLOAD_MODELS.get(stage)
        if model is None:
            raise AppError(
                code="STAGE_DETAIL_INVALID",
                message=f"未知的详情阶段：{stage}",
                status_code=422,
                details={"stage": stage, "allowed": list(STAGE_PAYLOAD_MODELS)},
            )
        row = self._get(user_id=user_id, application_id=application_id)
        try:
            validated = model.model_validate(payload.payload)
        except ValidationError as exc:
            raise AppError(
                code="STAGE_DETAIL_INVALID",
                message="详情字段校验失败",
                status_code=422,
                details={
                    "stage": stage,
                    "errors": [
                        {"location": list(error["loc"]), "message": error["msg"]}
                        for error in exc.errors()
                    ],
                },
            ) from None

        detail = self.repository.get_stage_detail(application_id=application_id, stage=stage)
        if detail is None:
            detail = ApplicationStageDetail(
                application_id=application_id,
                user_id=user_id,
                stage=stage,
                payload={},
            )
        detail.payload = validated.model_dump(mode="json")
        detail.occurred_at = payload.occurred_at or _now()
        self.repository.save_stage_detail(detail)

        application = row.application
        # Refreshing the parent keeps the list ordering honest (§3.4).
        application.updated_at = _now()
        self.repository.add_event(
            ApplicationEvent(
                application_id=application.id,
                user_id=user_id,
                event_type="stage_detail_updated",
                from_status=application.status.value,
                to_status=application.status.value,
                note=STAGE_LABELS.get(stage, stage),
            )
        )
        self._commit()
        return self._stage_read(detail)

    def delete_stage_detail(self, *, user_id: str, application_id: str, stage: str) -> None:
        self._get(user_id=user_id, application_id=application_id)
        detail = self.repository.get_stage_detail(application_id=application_id, stage=stage)
        if detail is None:
            raise AppError(
                code="STAGE_DETAIL_NOT_FOUND",
                message="该阶段还没有填写详情",
                status_code=404,
                details={"stage": stage},
            )
        self.repository.delete_stage_detail(detail)
        self.repository.add_event(
            ApplicationEvent(
                application_id=application_id,
                user_id=user_id,
                event_type="stage_detail_deleted",
                from_status=None,
                to_status=None,
                note=STAGE_LABELS.get(stage, stage),
            )
        )
        self._commit()

    # -- internals ---------------------------------------------------------
    def _create_from_positions(
        self, *, user_id: str, payload: ApplicationCreateRequest
    ) -> list[Application]:
        announcement = self.session.scalar(
            select(JobAnnouncement).where(
                JobAnnouncement.id == payload.announcement_id,
                JobAnnouncement.owner_user_id == user_id,
            )
        )
        if announcement is None:
            raise JobNotFoundError(str(payload.announcement_id))

        position_ids = list(dict.fromkeys(payload.position_ids))
        positions = list(
            self.session.scalars(
                select(JobPosition).where(
                    JobPosition.id.in_(position_ids),
                    JobPosition.announcement_id == announcement.id,
                )
            )
        )
        if len(positions) != len(position_ids):
            raise AppError(
                code="JOB_POSITION_NOT_FOUND",
                message="所选岗位不存在或不属于该公告",
                status_code=404,
                details={"announcement_id": announcement.id},
            )

        company_name = announcement.company.name if announcement.company else None
        applied_at = payload.applied_at
        if applied_at is None and payload.status.value in APPLIED_STATUSES:
            applied_at = _now()

        created: list[Application] = []
        for position in positions:
            existing = self.repository.get_by_position(user_id=user_id, position_id=position.id)
            if existing is not None:
                raise AppError(
                    code="APPLICATION_EXISTS",
                    message=f"「{position.title}」已经在投递记录中",
                    status_code=409,
                    details={"application_id": existing.id, "position_id": position.id},
                )
            created.append(
                Application(
                    user_id=user_id,
                    job_id=None,
                    announcement_id=announcement.id,
                    position_id=position.id,
                    company_name=company_name,
                    position_title=position.title,
                    status=payload.status,
                    channel=payload.channel,
                    contact_name=payload.contact_name,
                    contact_info=payload.contact_info,
                    link=payload.link or announcement.announcement_url,
                    notes=payload.notes,
                    next_follow_up_at=payload.follow_up_at,
                    applied_at=applied_at,
                    row_version=1,
                )
            )
            self.session.add(created[-1])

        try:
            self.session.flush()
            versions = ResumeVersionService(self.session)
            for application in created:
                self.session.add(
                    ApplicationEvent(
                        application_id=application.id,
                        user_id=user_id,
                        event_type="created",
                        from_status=None,
                        to_status=application.status.value,
                        note=payload.notes,
                    )
                )
                if application.status.value == "applied":
                    versions.lock_for_application(
                        user_id=user_id, application=application
                    )
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise AppError(
                code="APPLICATION_EXISTS",
                message="部分岗位已经在投递记录中",
                status_code=409,
            ) from None
        return created

    def _create_manual(
        self, *, user_id: str, payload: ApplicationCreateRequest
    ) -> Application:
        company_name = (payload.company_name or "").strip()
        position_title = (payload.position_title or "").strip()
        applied_at = payload.applied_at
        if applied_at is None and payload.status.value in APPLIED_STATUSES:
            applied_at = _now()

        if not payload.allow_duplicate:
            duplicate = self._find_duplicate(
                user_id=user_id,
                company_name=company_name,
                position_title=position_title,
                applied_at=applied_at,
            )
            if duplicate is not None:
                raise AppError(
                    code="APPLICATION_DUPLICATE_HINT",
                    message="已存在公司、岗位与投递日期都相同的记录",
                    status_code=409,
                    details={"application_id": duplicate.id},
                )

        application = Application(
            user_id=user_id,
            job_id=None,
            announcement_id=payload.announcement_id,
            position_id=None,
            company_name=company_name,
            position_title=position_title,
            status=payload.status,
            channel=payload.channel,
            contact_name=payload.contact_name,
            contact_info=payload.contact_info,
            link=payload.link,
            notes=payload.notes,
            next_follow_up_at=payload.follow_up_at,
            applied_at=applied_at,
            row_version=1,
        )
        self.repository.add(application)
        self.repository.add_event(
            ApplicationEvent(
                application_id=application.id,
                user_id=user_id,
                event_type="created",
                from_status=None,
                to_status=application.status.value,
                note=payload.notes,
            )
        )
        if application.status.value == "applied":
            ResumeVersionService(self.session).lock_for_application(
                user_id=user_id, application=application
            )
        self._commit()
        return application

    def _find_duplicate(
        self,
        *,
        user_id: str,
        company_name: str,
        position_title: str,
        applied_at: datetime | None,
    ) -> Application | None:
        candidates = self.session.scalars(
            select(Application).where(
                Application.user_id == user_id,
                Application.deleted_at.is_(None),
                Application.company_name == company_name,
                Application.position_title == position_title,
            )
        )
        target = _as_aware(applied_at).date() if applied_at else None
        for candidate in candidates:
            if target is None:
                return candidate
            stamp = candidate.applied_at or candidate.created_at
            if stamp and _as_aware(stamp).date() == target:
                return candidate
        return None

    @staticmethod
    def _apply_fields(application: Application, payload: ApplicationUpdateRequest) -> None:
        fields = payload.model_fields_set
        if "applied_at" in fields:
            application.applied_at = payload.applied_at
        if "follow_up_at" in fields:
            application.next_follow_up_at = payload.follow_up_at
        if "channel" in fields:
            application.channel = payload.channel
        if "contact_name" in fields:
            application.contact_name = payload.contact_name
        if "contact_info" in fields:
            application.contact_info = payload.contact_info
        if "link" in fields:
            application.link = payload.link
        if "notes" in fields:
            application.notes = payload.notes
        if "closed_reason" in fields:
            application.closed_reason = payload.closed_reason
        if "rejected_stage" in fields:
            application.rejected_stage = payload.rejected_stage

    def _get(self, *, user_id: str, application_id: str) -> ApplicationRow:
        row = self.repository.get(
            user_id=user_id,
            application_id=application_id,
            with_events=True,
        )
        if row is None:
            raise AppError(
                code="APPLICATION_NOT_FOUND",
                message="投递记录不存在或无权访问",
                status_code=404,
                details={"application_id": application_id},
            )
        return row

    def _commit(self) -> None:
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
        except Exception:
            self.session.rollback()
            raise

    @staticmethod
    def _sorted_details(
        details: list[ApplicationStageDetail],
    ) -> list[ApplicationStageDetail]:
        order = {stage: index for index, stage in enumerate(STAGE_LABELS)}
        return sorted(details, key=lambda item: order.get(item.stage, len(order)))

    @staticmethod
    def _stage_read(detail: ApplicationStageDetail) -> ApplicationStageDetailRead:
        return ApplicationStageDetailRead(
            id=detail.id,
            stage=detail.stage,  # type: ignore[arg-type]
            stage_label=STAGE_LABELS.get(detail.stage, detail.stage),
            payload=dict(detail.payload or {}),
            occurred_at=detail.occurred_at,
            created_at=detail.created_at,
            updated_at=detail.updated_at,
        )

    @staticmethod
    def _recommended_missing(
        application: Application, details: list[ApplicationStageDetail]
    ) -> list[str]:
        stage = {
            "written_test": "written_test",
            "interview_done": "interview",
            "offer": "offer",
        }.get(application.status.value)
        if stage is None:
            return []
        payload: dict[str, object] = {}
        for detail in details:
            if detail.stage == stage:
                payload = dict(detail.payload or {})
                break
        return [
            field
            for field in RECOMMENDED_FIELDS.get(stage, ())
            if payload.get(field) in (None, "", [], {})
        ]

    @staticmethod
    def _row(row: ApplicationRow) -> ApplicationRowSchema:
        application = row.application
        status = application.status.value
        terminal = is_terminal(status)
        follow_up = application.next_follow_up_at
        return ApplicationRowSchema(
            id=application.id,
            company_name=application.company_name
            or (row.job.company_name if row.job else "未知公司"),
            position_title=application.position_title
            or (row.job.title if row.job else "未命名岗位"),
            status=status,
            status_label=status_label(status),
            is_terminal=terminal,
            applied_at=application.applied_at,
            follow_up_at=follow_up,
            follow_up_due=bool(
                follow_up and not terminal and _as_aware(follow_up) <= _now()
            ),
            channel=application.channel,
            contact_name=application.contact_name,
            contact_info=application.contact_info,
            link=application.link,
            notes=application.notes,
            closed_reason=application.closed_reason,
            rejected_stage=application.rejected_stage,
            announcement_id=application.announcement_id,
            position_id=application.position_id,
            job_id=application.job_id,
            resume_id=application.resume_id,
            resume_version_id=application.resume_version_id,
            row_version=application.row_version or 1,
            created_at=application.created_at,
            updated_at=application.updated_at,
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime) -> datetime:
    """SQLite hands back naive datetimes; treat them as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _date_text(value: datetime | None) -> str:
    return _as_aware(value).date().isoformat() if value else ""


class PersonalizationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.applications = ApplicationRepository(session)
        self.documents = DocumentRepository(session)
        self.jobs = JobRepository(session)
        self.matching = MatchingService(session)

    def generate(
        self, *, user_id: str, job_id: str, resume_document_id: str
    ) -> PersonalizationResult:
        job = self.jobs.get(user_id=user_id, job_id=job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        resume = self.documents.get(
            user_id=user_id, document_id=resume_document_id, with_chunks=True
        )
        if resume is None:
            raise DocumentNotFoundError(resume_document_id)
        if resume.document_type != DocumentType.resume:
            raise AppError(
                code="RESUME_REQUIRED",
                message="个性化材料必须基于简历文档",
                status_code=422,
            )
        report = self.matching.build_report(
            user_id=user_id,
            job_id=job_id,
            resume_document_id=resume_document_id,
        )
        evidence_chunks = [
            chunk for chunk in resume.chunks if chunk.chunk_type in {"experience", "skill"}
        ] or list(resume.chunks)
        bullet_items = [
            ArtifactItem(
                text=f"可用于简历的事实：{chunk.content[:180]}",
                citations=[
                    Citation(
                        source_type="document_chunk",
                        source_id=chunk.id,
                        quote=chunk.content[:180],
                    )
                ],
            )
            for chunk in evidence_chunks[:3]
        ]
        gap_items = [
            ArtifactItem(
                text=f"优先补强 {skill}：完成一个可演示项目并记录量化结果。",
                citations=[Citation(source_type="job", source_id=job.id, quote=skill)],
            )
            for skill in report.missing_required_skills + report.missing_preferred_skills
        ][:5]
        if not gap_items:
            first = evidence_chunks[0]
            gap_items = [
                ArtifactItem(
                    text="结构化技能已覆盖当前要求，下一步补充可量化成果和部署证据。",
                    citations=[
                        Citation(
                            source_type="document_chunk",
                            source_id=first.id,
                            quote=first.content[:180],
                        )
                    ],
                )
            ]
        bullets = self._store(
            user_id=user_id,
            job=job,
            resume=resume,
            artifact_type=ArtifactType.resume_bullets,
            items=bullet_items,
        )
        gaps = self._store(
            user_id=user_id,
            job=job,
            resume=resume,
            artifact_type=ArtifactType.skill_gap_plan,
            items=gap_items,
        )
        try:
            self.session.commit()
            self.session.refresh(bullets)
            self.session.refresh(gaps)
        except Exception:
            self.session.rollback()
            raise
        return PersonalizationResult(
            resume_bullets=ArtifactRead.model_validate(bullets),
            skill_gap_plan=ArtifactRead.model_validate(gaps),
        )

    def _store(self, *, user_id, job, resume, artifact_type, items) -> GeneratedArtifact:
        citations = [citation for item in items for citation in item.citations]
        if not self._validate_citations(
            user_id=user_id, job=job, resume=resume, citations=citations
        ):
            raise AppError(
                code="CITATION_VALIDATION_FAILED",
                message="生成内容包含无法验证的引用，已阻止保存",
                status_code=422,
            )
        artifact = GeneratedArtifact(
            user_id=user_id,
            job_id=job.id,
            resume_document_id=resume.id,
            artifact_type=artifact_type,
            content=[item.model_dump(mode="json") for item in items],
            citations=[citation.model_dump(mode="json") for citation in citations],
            citation_valid=True,
            generator_version=GENERATOR_VERSION,
        )
        self.applications.add_artifact(artifact)
        return artifact

    @staticmethod
    def _validate_citations(*, user_id: str, job, resume, citations: list[Citation]) -> bool:
        if resume.user_id != user_id or job.user_id != user_id or not citations:
            return False
        chunks = {chunk.id: chunk for chunk in resume.chunks}
        job_facts = normalize_skills(job.required_skills + job.preferred_skills)
        for citation in citations:
            if citation.source_type == "document_chunk":
                chunk = chunks.get(citation.source_id)
                if chunk is None or citation.quote not in chunk.content:
                    return False
            elif citation.source_type == "job":
                if citation.source_id != job.id or (
                    citation.quote.lower() not in job_facts and citation.quote not in job.raw_text
                ):
                    return False
            else:
                return False
        return True


class AutofillService:
    """Create a reviewable field plan; it never submits an external application."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.applications = ApplicationRepository(session)
        self.documents = DocumentRepository(session)

    def plan(
        self, *, user_id: str, application_id: str, payload: AutofillRequest
    ) -> AutofillPlan:
        row = self.applications.get(user_id=user_id, application_id=application_id)
        if row is None:
            raise AppError(
                code="APPLICATION_NOT_FOUND",
                message="申请记录不存在或无权访问",
                status_code=404,
                details={"application_id": application_id},
            )
        resume = self.documents.get(
            user_id=user_id, document_id=payload.resume_document_id, with_chunks=True
        )
        if resume is None:
            raise DocumentNotFoundError(payload.resume_document_id)
        if resume.document_type != DocumentType.resume:
            raise AppError(code="RESUME_REQUIRED", message="自动填写必须基于简历文档", status_code=422)
        extracted = resume.extracted_data or {}
        profile = payload.profile or {}
        plans = [
            self._map_field(field, extracted, resume, row.job, profile)
            for field in payload.fields
        ]
        ready_count = sum(item.status == "ready" for item in plans)
        review_count = sum(item.status != "ready" for item in plans)
        run = AutofillRun(
            user_id=user_id,
            application_id=application_id,
            resume_document_id=resume.id,
            fields=[item.model_dump(mode="json") for item in plans],
            ready_count=ready_count,
            review_count=review_count,
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return AutofillPlan(
            run_id=run.id,
            application_id=application_id,
            job_id=row.job.id,
            resume_document_id=resume.id,
            fields=plans,
            ready_count=ready_count,
            review_count=review_count,
            generated_at=run.created_at,
        )

    @staticmethod
    def _map_field(
        field,
        extracted: dict[str, object],
        resume,
        job,
        profile: dict[str, object] | None = None,
    ) -> AutofillFieldPlan:
        label = f"{field.field_id} {field.label}".lower()
        if field.field_type == "file":
            return AutofillFieldPlan(
                field_id=field.field_id,
                label=field.label,
                value=None,
                confidence=0.0,
                status="unsupported",
                source_type="none",
                source_id=None,
                evidence=None,
                reason="文件上传由浏览器确认，计划不代替用户选择本地文件",
            )

        # Profile-first (plan §5.1): the browser-local profile beats the resume,
        # because the user has explicitly confirmed those fields.
        profile_value = _match_profile(label, profile or {})
        if profile_value:
            return AutofillFieldPlan(
                field_id=field.field_id,
                label=field.label,
                value=profile_value,
                confidence=0.99,
                status="ready",
                source_type="profile",
                source_id=None,
                evidence=profile_value,
                reason=None,
            )

        value: str | None = None
        evidence: str | None = None
        source_type = "none"
        source_id = None
        confidence = 0.0
        reason = None
        if any(token in label for token in ("email", "邮箱", "e-mail")):
            value = extracted.get("email")
            confidence = 0.99 if value else 0
        elif any(token in label for token in ("phone", "mobile", "电话", "手机")):
            value = extracted.get("phone")
            confidence = 0.99 if value else 0
        elif any(token in label for token in ("city", "location", "地点", "城市")):
            value = extracted.get("city") or (job.city if job.city else None)
            confidence = 0.92 if extracted.get("city") else 0.55 if value else 0
            source_type = "resume" if extracted.get("city") else "job"
            source_id = resume.id if extracted.get("city") else job.id
        elif any(token in label for token in ("linkedin", "github", "portfolio", "个人主页")):
            reason = "简历解析结果没有可信的主页 URL"
        elif any(token in label for token in ("name", "姓名", "full name")):
            first = next((line.strip() for line in resume.raw_text.splitlines() if line.strip()), None)
            value = first if first and len(first) <= 60 and not any(char.isdigit() for char in first) else None
            confidence = 0.65 if value else 0
        elif any(token in label for token in ("resume", "简历", "cv")):
            reason = "请确认上传哪一份简历文件"
        else:
            reason = "开放题或未识别字段必须人工确认，系统不会猜测个人事实"
        if value:
            source_type = source_type if source_type != "none" else "resume"
            source_id = source_id or resume.id
            evidence = value
            status = "ready" if confidence >= 0.9 else "review"
        else:
            status = "unsupported" if field.field_type == "file" else "review"
        if field.required and not value:
            reason = reason or "必填字段缺少可验证答案"
        return AutofillFieldPlan(
            field_id=field.field_id,
            label=field.label,
            value=str(value) if value is not None else None,
            confidence=confidence,
            status=status,
            source_type=source_type,
            source_id=source_id,
            evidence=evidence,
            reason=reason,
        )



def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _profile_text(container: dict[str, object], key: str) -> str | None:
    value = container.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _match_profile(label: str, profile: dict[str, object]) -> str | None:
    """Return the confirmed profile value for a form field, if any.

    Ordered specific → generic so ``email`` wins over ``name``. ``name`` is
    skipped for company/recruiter labels to avoid filling the wrong box.
    """
    basic = _as_dict(profile.get("basic"))
    links = _as_dict(profile.get("links"))
    preferences = _as_dict(profile.get("preferences"))
    education_raw = profile.get("education")
    education = education_raw if isinstance(education_raw, list) else []
    first_education = _as_dict(education[0]) if education else {}

    name_blocked = any(
        token in label for token in ("company", "公司", "last", "first", "middle", "recruiter")
    )

    checks: list[tuple[tuple[str, ...], str | None]] = [
        (("email", "邮箱", "e-mail"), _profile_text(basic, "email")),
        (("phone", "mobile", "电话", "手机"), _profile_text(basic, "phone")),
        (("wechat", "微信"), _profile_text(basic, "wechat")),
        (("school", "学校", "院校"), _profile_text(first_education, "school")),
        (("major", "专业"), _profile_text(first_education, "major")),
        (("degree", "学历"), _profile_text(first_education, "degree")),
        (("salary", "薪资", "期望"), _profile_text(preferences, "salary_expectation")),
        (("到岗", "available"), _profile_text(preferences, "available_from")),
        (("github",), _profile_text(links, "github")),
        (("portfolio", "作品集"), _profile_text(links, "portfolio")),
        (("blog", "博客"), _profile_text(links, "blog")),
        (("linkedin",), _profile_text(links, "linkedin")),
        (("city", "location", "地点", "城市"), _profile_text(basic, "city")),
        (("name", "姓名", "full name"), None if name_blocked else _profile_text(basic, "name")),
    ]
    for tokens, value in checks:
        if value and any(token in label for token in tokens):
            return value
    return None
