from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.content_security import scan_untrusted_content
from app.core.errors import (
    AppError,
    DocumentNotFoundError,
    DuplicateDocumentError,
    JobNotFoundError,
    ResumeExistsError,
    ResumeNotFoundError,
    ResumeOptimizationNotFoundError,
)
from app.domains.documents.model import DocumentType
from app.domains.documents.repository import DocumentRepository
from app.domains.documents.schemas import DocumentDetail, DocumentTextImport, ExtractedDocumentData
from app.domains.documents.service import DocumentService
from app.domains.jobs.repository import JobCatalogRepository, JobRepository
from app.domains.matching.skills import normalize_skill, normalize_skills
from app.domains.resumes.jd import JdProfile, resolve_jd_profile
from app.domains.resumes.matching import build_match_report
from app.domains.resumes.model import (
    OptimizationStatus,
    Resume,
    ResumeOptimization,
    ResumeSource,
    ResumeTemplate,
    ResumeVersion,
    ResumeVersionSource,
)
from app.domains.resumes.parser import (
    CORE_SECTIONS,
    RESUME_STRUCTURE_VERSION,
    ParsedResume,
    parse_resume_content,
    section_text,
)
from app.domains.resumes.render import to_html, to_markdown
from app.domains.resumes.repository import ResumeOptimizationRepository, ResumeRepository
from app.domains.resumes.schemas import (
    JdSnapshot,
    ResumeAnalysis,
    ResumeApplyRequest,
    ResumeApplyResult,
    ResumeCitation,
    ResumeDetail,
    ResumeDraft,
    ResumeEntry,
    ResumeFromDocument,
    ResumeHead,
    ResumeImportText,
    ResumeList,
    ResumeManualCreate,
    ResumeMatchReport,
    ResumeOptimizationList,
    ResumeOptimizationRead,
    ResumeOptimizationSummary,
    ResumeOptimizeRequest,
    ResumeSection,
    ResumeSuggestion,
    ResumeSummary,
    ResumeUpdate,
    ResumeVersionDetail,
    ResumeVersionList,
    ResumeVersionRead,
)
from app.domains.resumes.suggestions import (
    GENERATOR_VERSION,
    apply_suggestions,
    find_mismatched_rewrites,
    generate_suggestions,
)

DEFAULT_FONT_SIZE = 14
MANUAL_STRUCTURE_VERSION = "resume-manual-v1"


def resume_detail(resume: Resume) -> ResumeDetail:
    head = ResumeHead.model_validate(resume.head or {})
    sections = [ResumeSection.model_validate(section) for section in resume.sections or []]
    return ResumeDetail(
        id=resume.id,
        title=resume.title,
        template=resume.template,
        font_size=resume.font_size,
        target_job_id=resume.target_job_id,
        target_announcement_id=resume.target_announcement_id,
        source=resume.source,
        content_version=resume.content_version,
        document_id=resume.document_id,
        candidate_name=head.name,
        target_title=head.target_title,
        section_count=len(sections),
        entry_count=sum(len(section.entries) for section in sections),
        created_at=resume.created_at,
        updated_at=resume.updated_at,
        head=head,
        sections=sections,
        analysis=ResumeAnalysis.model_validate(resume.analysis or {}),
        optimization_count=len(resume.optimizations or []),
    )


def resume_summary(resume: Resume) -> ResumeSummary:
    head = ResumeHead.model_validate(resume.head or {})
    sections = resume.sections or []
    return ResumeSummary(
        id=resume.id,
        title=resume.title,
        template=resume.template,
        font_size=resume.font_size,
        target_job_id=resume.target_job_id,
        target_announcement_id=resume.target_announcement_id,
        source=resume.source,
        content_version=resume.content_version,
        document_id=resume.document_id,
        candidate_name=head.name,
        target_title=head.target_title,
        section_count=len(sections),
        entry_count=sum(len(section.get("entries") or []) for section in sections),
        created_at=resume.created_at,
        updated_at=resume.updated_at,
    )


class ResumeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ResumeRepository(session)
        self.documents = DocumentRepository(session)
        self.document_service = DocumentService(session)
        self.jobs = JobRepository(session)
        self.catalog = JobCatalogRepository(session)

    def import_text(self, *, user_id: str, payload: ResumeImportText) -> ResumeDetail:
        document = self._import_text_document(user_id=user_id, payload=payload)
        return self._create_from_document(
            user_id=user_id,
            document=document,
            title=payload.display_name,
            template=payload.template,
            target_job_id=payload.target_job_id,
            target_announcement_id=payload.target_announcement_id,
            source=ResumeSource.text,
        )

    def import_upload(
        self,
        *,
        user_id: str,
        display_name: str,
        file_name: str,
        content: bytes,
        template: ResumeTemplate,
        target_job_id: str | None = None,
        target_announcement_id: str | None = None,
    ) -> ResumeDetail:
        document = self._import_upload_document(
            user_id=user_id,
            display_name=display_name,
            file_name=file_name,
            content=content,
        )
        return self._create_from_document(
            user_id=user_id,
            document=document,
            title=display_name,
            template=template,
            target_job_id=target_job_id,
            target_announcement_id=target_announcement_id,
            source=ResumeSource.upload,
        )

    def create_from_document(
        self, *, user_id: str, payload: ResumeFromDocument
    ) -> ResumeDetail:
        document = self.documents.get(user_id=user_id, document_id=payload.document_id)
        if document is None:
            raise DocumentNotFoundError(payload.document_id)
        if document.document_type != DocumentType.resume:
            raise AppError(
                code="RESUME_DOCUMENT_REQUIRED",
                message="简历工作台需要简历类型文档",
                status_code=422,
                details={"document_id": payload.document_id},
            )
        existing = self.repository.get_by_document(
            user_id=user_id, document_id=payload.document_id
        )
        if existing is not None:
            raise ResumeExistsError(existing.id)
        return self._create_from_document(
            user_id=user_id,
            document=document,
            title=payload.title or document.display_name,
            template=payload.template,
            target_job_id=payload.target_job_id,
            target_announcement_id=payload.target_announcement_id,
            source=ResumeSource.manual,
        )

    def create_manual(self, *, user_id: str, payload: ResumeManualCreate) -> ResumeDetail:
        """Create an empty, fully editable resume with no source document."""
        self._validate_target_job(user_id=user_id, job_id=payload.target_job_id)
        self._validate_target_announcement(
            user_id=user_id, announcement_id=payload.target_announcement_id
        )
        head = payload.head or ResumeHead()
        sections = [
            ResumeSection(id=f"section-{key.value}", key=key, title=title, entries=[])
            for key, title in CORE_SECTIONS
        ]
        resume = Resume(
            user_id=user_id,
            document_id=None,
            title=payload.title[:200],
            template=payload.template,
            font_size=DEFAULT_FONT_SIZE,
            head=head.model_dump(mode="json"),
            sections=[section.model_dump(mode="json") for section in sections],
            target_job_id=payload.target_job_id,
            target_announcement_id=payload.target_announcement_id,
            source=ResumeSource.manual,
            content_version=1,
            analysis={
                "parser_version": MANUAL_STRUCTURE_VERSION,
                "source_document_id": None,
                "detected_section_titles": [title for _, title in CORE_SECTIONS],
                "warnings": [],
                "confidence": 1.0,
                "source_content_hash": None,
            },
        )
        try:
            self.repository.add(resume)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return resume_detail(resume)

    def list_resumes(self, *, user_id: str, page: int, page_size: int) -> ResumeList:
        resumes, total = self.repository.list(user_id=user_id, page=page, page_size=page_size)
        return ResumeList(
            items=[resume_summary(resume) for resume in resumes],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_resume(self, *, user_id: str, resume_id: str) -> ResumeDetail:
        return resume_detail(self._get_owned(user_id=user_id, resume_id=resume_id))

    def update_resume(
        self, *, user_id: str, resume_id: str, payload: ResumeUpdate
    ) -> ResumeDetail:
        resume = self._get_owned(user_id=user_id, resume_id=resume_id)
        changes = payload.model_dump(exclude_unset=True, mode="json")
        target_job_id = changes.get("target_job_id")
        self._validate_target_job(user_id=user_id, job_id=target_job_id)
        target_announcement_id = changes.get("target_announcement_id")
        self._validate_target_announcement(
            user_id=user_id, announcement_id=target_announcement_id
        )
        sections = changes.get("sections")
        if sections is not None:
            self._validate_structure(sections)
        for field, value in changes.items():
            setattr(resume, field, value)
        if "head" in changes or "sections" in changes:
            resume.content_version = (resume.content_version or 1) + 1
        try:
            self.session.commit()
            self.session.refresh(resume)
        except Exception:
            self.session.rollback()
            raise
        return resume_detail(resume)

    def reparse_resume(self, *, user_id: str, resume_id: str) -> ResumeDetail:
        resume = self._get_owned(user_id=user_id, resume_id=resume_id)
        if not resume.document_id:
            raise AppError(
                code="RESUME_SOURCE_MISSING",
                message="该简历没有关联原文，无法重新解析，请重新上传简历",
                status_code=409,
            )
        document = self.documents.get(user_id=user_id, document_id=resume.document_id)
        if document is None:
            raise DocumentNotFoundError(resume.document_id)
        parsed = parse_resume_content(raw_text=document.raw_text, display_name=resume.title)
        resume.head = parsed.head.model_dump(mode="json")
        resume.sections = [section.model_dump(mode="json") for section in parsed.sections]
        resume.analysis = self._analysis(document=document, parsed=parsed)
        resume.content_version = (resume.content_version or 1) + 1
        try:
            self.session.commit()
            self.session.refresh(resume)
        except Exception:
            self.session.rollback()
            raise
        return resume_detail(resume)

    def delete_resume(self, *, user_id: str, resume_id: str) -> None:
        resume = self._get_owned(user_id=user_id, resume_id=resume_id)
        try:
            self.repository.delete(resume)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def export_resume(self, *, user_id: str, resume_id: str, fmt: str) -> tuple[str, str]:
        resume = self._get_owned(user_id=user_id, resume_id=resume_id)
        head = ResumeHead.model_validate(resume.head or {})
        sections = [ResumeSection.model_validate(section) for section in resume.sections or []]
        if fmt == "html":
            return (
                to_html(title=resume.title, head=head, sections=sections),
                "text/html; charset=utf-8",
            )
        return (
            to_markdown(title=resume.title, head=head, sections=sections),
            "text/markdown; charset=utf-8",
        )

    def _import_text_document(
        self, *, user_id: str, payload: ResumeImportText
    ) -> DocumentDetail:
        try:
            return self.document_service.import_text(
                user_id=user_id,
                payload=DocumentTextImport(
                    display_name=payload.display_name,
                    document_type=DocumentType.resume,
                    raw_text=payload.raw_text,
                ),
            )
        except DuplicateDocumentError as error:
            return self._existing_document(
                user_id=user_id,
                document_id=str(error.details.get("existing_document_id", "")),
            )

    def _import_upload_document(
        self, *, user_id: str, display_name: str, file_name: str, content: bytes
    ) -> DocumentDetail:
        try:
            return self.document_service.import_upload(
                user_id=user_id,
                display_name=display_name,
                document_type=DocumentType.resume,
                file_name=file_name,
                content=content,
            )
        except DuplicateDocumentError as error:
            return self._existing_document(
                user_id=user_id,
                document_id=str(error.details.get("existing_document_id", "")),
            )

    def _existing_document(self, *, user_id: str, document_id: str) -> DocumentDetail:
        existing_resume = self.repository.get_by_document(
            user_id=user_id, document_id=document_id
        )
        if existing_resume is not None:
            raise ResumeExistsError(existing_resume.id)
        return self.document_service.get_document(user_id=user_id, document_id=document_id)

    def _create_from_document(
        self,
        *,
        user_id: str,
        document: DocumentDetail,
        title: str,
        template: ResumeTemplate,
        target_job_id: str | None,
        target_announcement_id: str | None = None,
        source: ResumeSource,
    ) -> ResumeDetail:
        existing = self.repository.get_by_document(user_id=user_id, document_id=document.id)
        if existing is not None:
            raise ResumeExistsError(existing.id)
        self._validate_target_job(user_id=user_id, job_id=target_job_id)
        self._validate_target_announcement(
            user_id=user_id, announcement_id=target_announcement_id
        )
        parsed = parse_resume_content(raw_text=document.raw_text, display_name=title)
        resume = Resume(
            user_id=user_id,
            document_id=document.id,
            title=title[:200],
            template=template,
            font_size=DEFAULT_FONT_SIZE,
            head=parsed.head.model_dump(mode="json"),
            sections=[section.model_dump(mode="json") for section in parsed.sections],
            target_job_id=target_job_id,
            target_announcement_id=target_announcement_id,
            source=source,
            content_version=1,
            analysis=self._analysis(document=document, parsed=parsed),
        )
        try:
            self.repository.add(resume)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return resume_detail(resume)

    @staticmethod
    def _analysis(document: DocumentDetail, parsed: ParsedResume) -> dict[str, object]:
        return {
            "parser_version": RESUME_STRUCTURE_VERSION,
            "source_document_id": document.id,
            "detected_section_titles": parsed.detected_section_titles,
            "warnings": parsed.warnings,
            "confidence": parsed.confidence,
            "source_content_hash": document.content_hash,
        }

    @staticmethod
    def _validate_structure(sections: list[dict[str, object]]) -> None:
        section_ids = [section.get("id") for section in sections]
        if len(set(section_ids)) != len(section_ids):
            raise AppError(
                code="INVALID_RESUME_STRUCTURE",
                message="简历章节 ID 不能重复",
                status_code=422,
            )
        entry_ids = [
            entry.get("id")
            for section in sections
            for entry in section.get("entries") or []
        ]
        if len(set(entry_ids)) != len(entry_ids):
            raise AppError(
                code="INVALID_RESUME_STRUCTURE",
                message="简历条目 ID 不能重复",
                status_code=422,
            )

    def _get_owned(self, *, user_id: str, resume_id: str) -> Resume:
        resume = self.repository.get(user_id=user_id, resume_id=resume_id)
        if resume is None:
            raise ResumeNotFoundError(resume_id)
        return resume

    def _validate_target_job(self, *, user_id: str, job_id: str | None) -> None:
        if job_id and self.jobs.get(user_id=user_id, job_id=job_id) is None:
            raise JobNotFoundError(job_id)

    def _validate_target_announcement(
        self, *, user_id: str, announcement_id: str | None
    ) -> None:
        """Announcement targets must belong to the caller (module 1 catalog)."""

        if not announcement_id:
            return
        announcement = self.catalog.get(user_id=user_id, announcement_id=announcement_id)
        if announcement is None:
            raise AppError(
                code="JOB_ANNOUNCEMENT_NOT_FOUND",
                message="目标职位公告不存在或无权访问",
                status_code=404,
                details={"announcement_id": announcement_id},
            )


class ResumeVersionService:
    """Locked snapshots so a submission can be replayed exactly as sent."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.resumes = ResumeRepository(session)

    def list_for_resume(self, *, user_id: str, resume_id: str) -> ResumeVersionList:
        self._get_resume(user_id=user_id, resume_id=resume_id)
        rows = list(
            self.session.scalars(
                select(ResumeVersion)
                .where(
                    ResumeVersion.user_id == user_id,
                    ResumeVersion.resume_id == resume_id,
                )
                .order_by(ResumeVersion.version_no.desc())
            )
        )
        return ResumeVersionList(
            items=[ResumeVersionRead.model_validate(row) for row in rows],
            total=len(rows),
        )

    def get_version(
        self, *, user_id: str, resume_id: str, version_no: int
    ) -> ResumeVersionDetail:
        row = self.session.scalar(
            select(ResumeVersion).where(
                ResumeVersion.user_id == user_id,
                ResumeVersion.resume_id == resume_id,
                ResumeVersion.version_no == version_no,
            )
        )
        if row is None:
            raise AppError(
                code="RESUME_VERSION_NOT_FOUND",
                message="简历版本不存在或已删除",
                status_code=404,
                details={"resume_id": resume_id, "version_no": version_no},
            )
        return ResumeVersionDetail(
            id=row.id,
            resume_id=row.resume_id,
            version_no=row.version_no,
            source=row.source,
            note=row.note,
            created_at=row.created_at,
            head=ResumeHead.model_validate(row.head or {}),
            sections=[
                ResumeSection.model_validate(section) for section in row.sections or []
            ],
        )

    def lock(
        self,
        *,
        user_id: str,
        resume: Resume,
        source: ResumeVersionSource = ResumeVersionSource.locked,
        optimization_id: str | None = None,
        note: str | None = None,
    ) -> ResumeVersion:
        """Snapshot the resume as-is. Caller owns the transaction (flush only)."""

        latest = self.session.scalar(
            select(func.max(ResumeVersion.version_no)).where(
                ResumeVersion.resume_id == resume.id
            )
        )
        version = ResumeVersion(
            user_id=user_id,
            resume_id=resume.id,
            version_no=int(latest or 0) + 1,
            head=resume.head,
            sections=resume.sections,
            source=source,
            optimization_id=optimization_id,
            note=note,
        )
        self.session.add(version)
        self.session.flush()
        return version

    def lock_for_application(self, *, user_id: str, application) -> ResumeVersion | None:
        """Attach a snapshot the first time an application reaches ``applied``."""

        if application.resume_version_id:
            existing = self.session.get(ResumeVersion, application.resume_version_id)
            if existing is not None:
                return existing
        resume = self._pick_resume(user_id=user_id, application=application)
        if resume is None:
            return None
        version = self.lock(
            user_id=user_id,
            resume=resume,
            source=ResumeVersionSource.locked,
            note=f"投递 {application.company_name or ''} {application.position_title or ''}".strip(),
        )
        application.resume_id = resume.id
        application.resume_version_id = version.id
        return version

    def version_read(self, *, user_id: str, version_id: str | None) -> ResumeVersionRead | None:
        if not version_id:
            return None
        row = self.session.scalar(
            select(ResumeVersion).where(
                ResumeVersion.id == version_id, ResumeVersion.user_id == user_id
            )
        )
        return ResumeVersionRead.model_validate(row) if row is not None else None

    def _pick_resume(self, *, user_id: str, application) -> Resume | None:
        """Prefer the resume that targets the same announcement, else the newest."""

        statement = select(Resume).where(Resume.user_id == user_id)
        if application.announcement_id:
            targeted = self.session.scalar(
                statement.where(
                    Resume.target_announcement_id == application.announcement_id
                ).order_by(Resume.updated_at.desc())
            )
            if targeted is not None:
                return targeted
        return self.session.scalar(statement.order_by(Resume.updated_at.desc()))

    def _get_resume(self, *, user_id: str, resume_id: str) -> Resume:
        resume = self.resumes.get(user_id=user_id, resume_id=resume_id)
        if resume is None:
            raise ResumeNotFoundError(resume_id)
        return resume


class ResumeOptimizationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.resumes = ResumeRepository(session)
        self.optimizations = ResumeOptimizationRepository(session)
        self.documents = DocumentRepository(session)

    def optimize(
        self, *, user_id: str, resume_id: str, payload: ResumeOptimizeRequest
    ) -> ResumeOptimizationRead:
        resume = self._get_resume(user_id=user_id, resume_id=resume_id)
        head = ResumeHead.model_validate(resume.head or {})
        sections = [ResumeSection.model_validate(section) for section in resume.sections or []]
        document = self._resume_document(user_id=user_id, resume=resume)
        resume_profile = (
            ExtractedDocumentData.model_validate(document.extracted_data)
            if document is not None
            else None
        )
        jd = resolve_jd_profile(self.session, user_id=user_id, payload=payload)
        security = scan_untrusted_content(jd.raw_text)
        if security.prompt_injection_detected:
            raise AppError(
                code="JD_CONTENT_BLOCKED",
                message="JD 文本包含疑似提示词注入，已阻止生成简历优化建议",
                status_code=422,
                details={"flags": security.flags},
            )
        report = build_match_report(
            head=head, sections=sections, jd=jd, resume_profile=resume_profile
        )
        suggestions = generate_suggestions(
            sections=sections, jd=jd, report=report, focus=payload.focus
        )
        self._validate_citations(jd=jd, head=head, sections=sections, suggestions=suggestions)
        draft_head, draft_sections, applied_ids = apply_suggestions(
            head=head.model_copy(deep=True),
            sections=[section.model_copy(deep=True) for section in sections],
            suggestions=suggestions,
        )
        optimization = ResumeOptimization(
            user_id=user_id,
            resume_id=resume.id,
            job_id=jd.job_id,
            announcement_id=jd.announcement_id,
            jd_document_id=jd.document_id,
            status=OptimizationStatus.generated,
            jd_snapshot=jd.snapshot().model_dump(mode="json"),
            match_report=report.model_dump(mode="json"),
            suggestions=[item.model_dump(mode="json") for item in suggestions],
            draft=ResumeDraft(
                head=draft_head,
                sections=draft_sections,
                applied_suggestion_ids=applied_ids,
            ).model_dump(mode="json"),
            base_content_version=resume.content_version,
            generator_version=GENERATOR_VERSION,
            prompt_injection_detected=False,
            security_flags=[],
        )
        try:
            self.optimizations.add(optimization)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return self._read(optimization)

    def list_optimizations(
        self, *, user_id: str, resume_id: str
    ) -> ResumeOptimizationList:
        self._get_resume(user_id=user_id, resume_id=resume_id)
        rows = self.optimizations.list_for_resume(user_id=user_id, resume_id=resume_id)
        items = [self._summary(row) for row in rows]
        return ResumeOptimizationList(items=items, total=len(items))

    def get_optimization(
        self, *, user_id: str, resume_id: str, optimization_id: str
    ) -> ResumeOptimizationRead:
        return self._read(
            self._get_optimization(
                user_id=user_id, resume_id=resume_id, optimization_id=optimization_id
            )
        )

    def apply(
        self,
        *,
        user_id: str,
        resume_id: str,
        optimization_id: str,
        payload: ResumeApplyRequest,
    ) -> ResumeApplyResult:
        resume = self._get_resume(user_id=user_id, resume_id=resume_id)
        optimization = self._get_optimization(
            user_id=user_id, resume_id=resume_id, optimization_id=optimization_id
        )
        if optimization.status == OptimizationStatus.applied:
            raise AppError(
                code="OPTIMIZATION_ALREADY_APPLIED",
                message="该优化建议已经应用过，请重新生成新的建议",
                status_code=409,
                details={"optimization_id": optimization.id},
            )
        if optimization.status != OptimizationStatus.generated:
            raise AppError(
                code="OPTIMIZATION_NOT_APPLICABLE",
                message="该优化记录已失效，请重新生成建议",
                status_code=409,
                details={"optimization_id": optimization.id, "status": optimization.status.value},
            )
        if resume.content_version != optimization.base_content_version:
            raise AppError(
                code="RESUME_CHANGED",
                message="简历在生成建议后被修改，请重新生成优化建议",
                status_code=409,
                details={
                    "resume_version": resume.content_version,
                    "optimization_version": optimization.base_content_version,
                },
            )
        suggestions = [
            ResumeSuggestion.model_validate(item) for item in optimization.suggestions
        ]
        selected = self._select_suggestions(suggestions=suggestions, payload=payload)
        blocked = [item.id for item in selected if not item.applicable]
        if blocked:
            raise AppError(
                code="SUGGESTION_REQUIRES_NEW_FACT",
                message="选中的建议需要补充真实经历，系统不会自动写入简历",
                status_code=422,
                details={"suggestion_ids": blocked},
            )
        sections = [ResumeSection.model_validate(section) for section in resume.sections or []]
        mismatched = find_mismatched_rewrites(sections=sections, suggestions=selected)
        if mismatched:
            raise AppError(
                code="SUGGESTION_OUT_OF_DATE",
                message="简历内容与建议原文不再一致，请重新生成优化建议",
                status_code=409,
                details={"suggestion_ids": mismatched},
            )
        head = ResumeHead.model_validate(resume.head or {})
        new_head, new_sections, applied_ids = apply_suggestions(
            head=head.model_copy(deep=True),
            sections=[section.model_copy(deep=True) for section in sections],
            suggestions=selected,
        )
        if not applied_ids:
            raise AppError(
                code="NOTHING_TO_APPLY",
                message="没有可应用到简历的建议，请重新生成或手动编辑",
                status_code=422,
            )
        optimization.before_apply_snapshot = {
            "head": resume.head,
            "sections": resume.sections,
        }
        optimization.applied_suggestion_ids = applied_ids
        optimization.status = OptimizationStatus.applied
        optimization.applied_at = datetime.now(timezone.utc)
        resume.head = new_head.model_dump(mode="json")
        resume.sections = [section.model_dump(mode="json") for section in new_sections]
        resume.content_version = (resume.content_version or 1) + 1
        if optimization.job_id:
            resume.target_job_id = optimization.job_id
        try:
            self.session.commit()
            self.session.refresh(resume)
            self.session.refresh(optimization)
        except Exception:
            self.session.rollback()
            raise
        return ResumeApplyResult(
            resume=resume_detail(resume),
            optimization=self._read(optimization),
            applied_suggestion_ids=applied_ids,
        )

    def revert(self, *, user_id: str, resume_id: str, optimization_id: str) -> ResumeDetail:
        resume = self._get_resume(user_id=user_id, resume_id=resume_id)
        optimization = self._get_optimization(
            user_id=user_id, resume_id=resume_id, optimization_id=optimization_id
        )
        if optimization.status != OptimizationStatus.applied:
            raise AppError(
                code="OPTIMIZATION_NOT_APPLIED",
                message="只有已经应用的建议才支持撤销",
                status_code=409,
            )
        if resume.content_version != (optimization.base_content_version or 1) + 1:
            raise AppError(
                code="RESUME_CHANGED_AFTER_APPLY",
                message="简历在应用建议后又被修改，无法自动撤销",
                status_code=409,
                details={"resume_version": resume.content_version},
            )
        snapshot = optimization.before_apply_snapshot or {}
        if not snapshot.get("sections"):
            raise AppError(
                code="OPTIMIZATION_SNAPSHOT_MISSING",
                message="该优化记录缺少应用前快照，无法撤销",
                status_code=409,
            )
        resume.head = snapshot.get("head") or resume.head
        resume.sections = snapshot["sections"]
        resume.content_version = (resume.content_version or 1) + 1
        optimization.status = OptimizationStatus.reverted
        try:
            self.session.commit()
            self.session.refresh(resume)
        except Exception:
            self.session.rollback()
            raise
        return resume_detail(resume)

    def discard(
        self, *, user_id: str, resume_id: str, optimization_id: str
    ) -> ResumeOptimizationRead:
        optimization = self._get_optimization(
            user_id=user_id, resume_id=resume_id, optimization_id=optimization_id
        )
        if optimization.status == OptimizationStatus.applied:
            raise AppError(
                code="OPTIMIZATION_ALREADY_APPLIED",
                message="已经应用到简历的建议不能丢弃，请先撤销",
                status_code=409,
            )
        optimization.status = OptimizationStatus.discarded
        try:
            self.session.commit()
            self.session.refresh(optimization)
        except Exception:
            self.session.rollback()
            raise
        return self._read(optimization)

    @staticmethod
    def _select_suggestions(
        *, suggestions: list[ResumeSuggestion], payload: ResumeApplyRequest
    ) -> list[ResumeSuggestion]:
        by_id = {item.id: item for item in suggestions}
        if payload.suggestion_ids:
            unknown = [item for item in payload.suggestion_ids if item not in by_id]
            if unknown:
                raise AppError(
                    code="UNKNOWN_SUGGESTION",
                    message="存在无法识别的建议编号",
                    status_code=422,
                    details={"suggestion_ids": unknown},
                )
            return [by_id[item] for item in payload.suggestion_ids]
        applicable = [item for item in suggestions if item.applicable]
        if not applicable:
            raise AppError(
                code="NOTHING_TO_APPLY",
                message="这次生成的建议都需要补充真实经历，请手动编辑简历",
                status_code=422,
            )
        return applicable

    @staticmethod
    def _validate_citations(
        *,
        jd: JdProfile,
        head: ResumeHead,
        sections: list[ResumeSection],
        suggestions: list[ResumeSuggestion],
    ) -> None:
        entry_map = {entry.id: entry for section in sections for entry in section.entries}
        section_map = {section.id: section for section in sections}
        capabilities = normalize_skills(jd.required_skills + jd.preferred_skills)
        head_text = "\n".join(
            filter(
                None,
                [
                    head.name,
                    head.target_title,
                    head.phone,
                    head.email,
                    head.city,
                    *[link.url for link in head.links],
                ],
            )
        )
        invalid: list[str] = []
        for suggestion in suggestions:
            if not suggestion.citations:
                invalid.append(suggestion.id)
                continue
            for citation in suggestion.citations:
                if not ResumeOptimizationService._citation_valid(
                    citation=citation,
                    jd=jd,
                    capabilities=capabilities,
                    head_text=head_text,
                    entry_map=entry_map,
                    section_map=section_map,
                ):
                    invalid.append(suggestion.id)
                    break
        if invalid:
            raise AppError(
                code="CITATION_VALIDATION_FAILED",
                message="生成的建议包含无法验证的引用，已阻止保存",
                status_code=422,
                details={"suggestion_ids": invalid},
            )

    @staticmethod
    def _citation_valid(
        *,
        citation: ResumeCitation,
        jd: JdProfile,
        capabilities: set[str],
        head_text: str,
        entry_map: dict[str, ResumeEntry],
        section_map: dict[str, ResumeSection],
    ) -> bool:
        source_type = citation.source_type
        if source_type == "resume_entry":
            entry = entry_map.get(citation.source_id)
            if entry is None:
                return False
            corpus = "\n".join(
                filter(
                    None,
                    [entry.title, entry.subtitle, entry.period or "", *entry.bullets],
                )
            )
            return citation.quote in corpus
        if source_type == "resume_section":
            section = section_map.get(citation.source_id)
            return section is not None and citation.quote in section_text(section)
        if source_type == "resume_head":
            return citation.quote in head_text
        if source_type == "job":
            return citation.source_id == jd.job_id and (
                citation.quote in jd.raw_text or normalize_skill(citation.quote) in capabilities
            )
        if source_type == "announcement":
            return citation.source_id == jd.announcement_id and (
                citation.quote in jd.raw_text or normalize_skill(citation.quote) in capabilities
            )
        if source_type == "jd_document":
            return citation.source_id == jd.document_id and (
                citation.quote in jd.raw_text or normalize_skill(citation.quote) in capabilities
            )
        return citation.quote in jd.raw_text or normalize_skill(citation.quote) in capabilities

    def _read(self, optimization: ResumeOptimization) -> ResumeOptimizationRead:
        jd = JdSnapshot.model_validate(optimization.jd_snapshot or {})
        report = ResumeMatchReport.model_validate(optimization.match_report or {})
        suggestions = [
            ResumeSuggestion.model_validate(item) for item in optimization.suggestions or []
        ]
        draft = ResumeDraft.model_validate(
            optimization.draft
            or {"head": ResumeHead(), "sections": [], "applied_suggestion_ids": []}
        )
        applicable = sum(1 for item in suggestions if item.applicable)
        return ResumeOptimizationRead(
            id=optimization.id,
            resume_id=optimization.resume_id,
            status=optimization.status,
            job_id=optimization.job_id,
            announcement_id=optimization.announcement_id,
            jd_document_id=optimization.jd_document_id,
            jd_title=jd.title,
            total_score=report.total_score,
            suggestion_count=len(suggestions),
            applicable_count=applicable,
            created_at=optimization.created_at,
            applied_at=optimization.applied_at,
            jd=jd,
            match_report=report,
            suggestions=suggestions,
            draft=draft,
            requires_review_count=len(suggestions) - applicable,
            base_content_version=optimization.base_content_version,
            applied_suggestion_ids=list(optimization.applied_suggestion_ids or []),
            generator_version=optimization.generator_version,
            prompt_injection_detected=optimization.prompt_injection_detected,
            security_flags=list(optimization.security_flags or []),
        )

    @staticmethod
    def _summary(optimization: ResumeOptimization) -> ResumeOptimizationSummary:
        jd = JdSnapshot.model_validate(optimization.jd_snapshot or {})
        report = ResumeMatchReport.model_validate(optimization.match_report or {})
        suggestions = optimization.suggestions or []
        return ResumeOptimizationSummary(
            id=optimization.id,
            resume_id=optimization.resume_id,
            status=optimization.status,
            job_id=optimization.job_id,
            announcement_id=optimization.announcement_id,
            jd_document_id=optimization.jd_document_id,
            jd_title=jd.title,
            total_score=report.total_score,
            suggestion_count=len(suggestions),
            applicable_count=sum(1 for item in suggestions if item.get("applicable")),
            created_at=optimization.created_at,
            applied_at=optimization.applied_at,
        )

    def _get_resume(self, *, user_id: str, resume_id: str) -> Resume:
        resume = self.resumes.get(user_id=user_id, resume_id=resume_id)
        if resume is None:
            raise ResumeNotFoundError(resume_id)
        return resume

    def _get_optimization(
        self, *, user_id: str, resume_id: str, optimization_id: str
    ) -> ResumeOptimization:
        optimization = self.optimizations.get(
            user_id=user_id, resume_id=resume_id, optimization_id=optimization_id
        )
        if optimization is None:
            raise ResumeOptimizationNotFoundError(optimization_id)
        return optimization

    def _resume_document(self, *, user_id: str, resume: Resume):
        if not resume.document_id:
            return None
        return self.documents.get(user_id=user_id, document_id=resume.document_id)


__all__ = [
    "ResumeOptimizationService",
    "ResumeService",
    "ResumeVersionService",
    "resume_detail",
    "resume_summary",
]
