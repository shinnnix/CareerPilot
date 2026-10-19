from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, DocumentNotFoundError, JobNotFoundError
from app.domains.applications.model import (
    Application,
    ApplicationEvent,
    ApplicationStatus,
    ArtifactType,
    AutofillRun,
    GeneratedArtifact,
    MatchFeedback,
)
from app.domains.applications.repository import ApplicationRepository, ApplicationRow
from app.domains.applications.schemas import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationList,
    ApplicationRead,
    ApplicationUpdate,
    ArtifactItem,
    ArtifactRead,
    AutofillFieldPlan,
    AutofillPlan,
    AutofillRequest,
    Citation,
    FeedbackRead,
    FeedbackUpsert,
    PersonalizationResult,
)
from app.domains.documents.model import DocumentType
from app.domains.documents.repository import DocumentRepository
from app.domains.jobs.repository import JobRepository
from app.domains.matching.service import MatchingService
from app.domains.matching.skills import normalize_skills

GENERATOR_VERSION = "evidence-template-v1"
AUTOFILL_VERSION = "autofill-rules-v1"

ALLOWED_TRANSITIONS = {
    ApplicationStatus.saved: {
        ApplicationStatus.preparing,
        ApplicationStatus.applied,
        ApplicationStatus.withdrawn,
    },
    ApplicationStatus.preparing: {
        ApplicationStatus.saved,
        ApplicationStatus.applied,
        ApplicationStatus.withdrawn,
    },
    ApplicationStatus.applied: {
        ApplicationStatus.interview,
        ApplicationStatus.rejected,
        ApplicationStatus.withdrawn,
    },
    ApplicationStatus.interview: {
        ApplicationStatus.offer,
        ApplicationStatus.rejected,
        ApplicationStatus.withdrawn,
    },
    ApplicationStatus.offer: {ApplicationStatus.withdrawn},
    ApplicationStatus.rejected: set(),
    ApplicationStatus.withdrawn: set(),
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
            status=payload.status,
            notes=payload.notes,
            applied_at=(
                datetime.now(timezone.utc) if payload.status == ApplicationStatus.applied else None
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
            if payload.status not in ALLOWED_TRANSITIONS[old_status]:
                raise AppError(
                    code="INVALID_APPLICATION_TRANSITION",
                    message=f"申请状态不能从 {old_status.value} 变为 {payload.status.value}",
                    status_code=409,
                )
            application.status = payload.status
            if payload.status == ApplicationStatus.applied and application.applied_at is None:
                application.applied_at = datetime.now(timezone.utc)
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
            job_title=row.job.title,
            company_name=row.job.company_name,
            status=application.status,
            notes=application.notes,
            applied_at=application.applied_at,
            created_at=application.created_at,
            updated_at=application.updated_at,
        )


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
        plans = [self._map_field(field, extracted, resume, row.job) for field in payload.fields]
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
    def _map_field(field, extracted: dict[str, object], resume, job) -> AutofillFieldPlan:
        label = f"{field.field_id} {field.label}".lower()
        value: str | None = None
        evidence: str | None = None
        source_type = "none"
        source_id = None
        confidence = 0.0
        reason = None
        if field.field_type == "file":
            reason = "文件上传由浏览器确认，计划不代替用户选择本地文件"
        elif any(token in label for token in ("email", "邮箱", "e-mail")):
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

