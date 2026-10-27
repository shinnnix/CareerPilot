from __future__ import annotations

import csv
import hashlib
import io
from datetime import date, datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, JobNotFoundError
from app.domains.ai.extraction import enhance_announcement
from app.domains.ai.schemas import AiConfig
from app.domains.applications.model import Application
from app.domains.documents.file_text import extract_text_from_upload
from app.domains.jobs.adapters.wechat_article import fetch_article
from app.domains.jobs.announcement_parser import parse_announcement, positions_text
from app.domains.jobs.constants import (
    COMPANY_TYPES,
    DEFAULT_VISIBLE_COLUMNS,
    FILTERABLE_STATUSES,
    JOB_TABLE_KEY,
    RECRUITMENT_TYPES,
    TABLE_COLUMNS,
    derive_row_status,
    status_label,
)
from app.domains.jobs.model import (
    AnnouncementSource,
    Company,
    Job,
    JobAnnouncement,
    JobImport,
    JobPosition,
    JobStatus,
    UserJobMark,
)
from app.domains.jobs.repository import JobCatalogRepository, JobRepository
from app.domains.jobs.schemas import (
    ColumnOption,
    DeadlineInfo,
    FacetOption,
    JobAnnouncementDetail,
    JobCatalogList,
    JobCatalogQuery,
    JobCreate,
    JobFacets,
    JobImportConfirm,
    JobImportList,
    JobImportRead,
    JobList,
    JobMarkBatch,
    JobMarkRead,
    JobMarkUpdate,
    JobPositionRead,
    JobRead,
    JobRow,
    JobRowCompany,
    JobSourceInfo,
    JobTablePreference,
    JobUpdate,
)

COLUMN_LABELS = {
    "company_name": "公司名称",
    "company_type": "公司类型",
    "recruitment_type": "招聘类型",
    "target_cohort": "招聘对象",
    "location": "工作地点",
    "positions": "岗位",
    "updated_at": "更新时间",
    "deadline": "投递截止",
    "announcement": "招聘公告",
    "company_scale": "公司规模",
    "mark_status": "状态",
}

PREVIEW_LIMIT = 120
MAX_RAW_TEXT = 200_000


class JobService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = JobRepository(session)

    def list_jobs(
        self,
        *,
        user_id: str,
        keyword: str | None,
        city: str | None,
        status: JobStatus | None,
        page: int,
        page_size: int,
    ) -> JobList:
        jobs, total = self.repository.list(
            user_id=user_id,
            keyword=keyword,
            city=city,
            status=status,
            page=page,
            page_size=page_size,
        )
        return JobList(
            items=[JobRead.model_validate(job) for job in jobs],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_job(self, *, user_id: str, job_id: str) -> JobRead:
        # .model_validate(data) 校验字典 / ORM 对象，生成模型实例，
        # 可选参数from_attributes=True可以直接把数据库 ORM 对象转为 Pydantic 模型
        return JobRead.model_validate(self._get_owned_job(user_id=user_id, job_id=job_id))

    def create_job(self, *, user_id: str, payload: JobCreate) -> JobRead:
        values = payload.model_dump()
        if values.get("source_url") is not None:
            values["source_url"] = str(values["source_url"])
        job = Job(user_id=user_id, **values)
        try:
            self.repository.add(job)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return JobRead.model_validate(job)

    def update_job(self, *, user_id: str, job_id: str, payload: JobUpdate) -> JobRead:
        job = self._get_owned_job(user_id=user_id, job_id=job_id)
        changes = payload.model_dump(exclude_unset=True)
        if "source_url" in changes and changes["source_url"] is not None:
            changes["source_url"] = str(changes["source_url"])

        prospective_min = changes.get("salary_min", job.salary_min)
        prospective_max = changes.get("salary_max", job.salary_max)
        if (
            prospective_min is not None
            and prospective_max is not None
            and prospective_min > prospective_max
        ):
            from app.core.errors import AppError

            raise AppError(
                code="INVALID_SALARY_RANGE",
                message="最低薪资不能高于最高薪资",
                status_code=422,
            )

        for field, value in changes.items():
            setattr(job, field, value)
        try:
            self.session.commit()
            self.session.refresh(job)
        except Exception:
            self.session.rollback()
            raise
        return JobRead.model_validate(job)

    def delete_job(self, *, user_id: str, job_id: str) -> None:
        job = self._get_owned_job(user_id=user_id, job_id=job_id)
        application_id = self.session.scalar(
            select(Application.id).where(
                Application.user_id == user_id, Application.job_id == job_id
            )
        )
        if application_id:
            raise AppError(
                code="JOB_HAS_APPLICATION",
                message="职位已有申请历史，请保留职位或先处理申请记录",
                status_code=409,
                details={"application_id": application_id},
            )
        try:
            self.repository.delete(job)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def _get_owned_job(self, *, user_id: str, job_id: str) -> Job:
        job = self.repository.get(user_id=user_id, job_id=job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job


class JobCatalogService:
    """Module 1: announcement-level catalog with derived application status."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = JobCatalogRepository(session)

    # -- listing ---------------------------------------------------------
    def list_catalog(self, *, user_id: str, query: JobCatalogQuery) -> JobCatalogList:
        page_ids, total = self.repository.page(user_id=user_id, query=query)
        stats = self.repository.application_stats(
            user_id=user_id, announcement_ids=page_ids
        )
        marks = self.repository.marks(user_id=user_id, announcement_ids=page_ids)
        announcements = self.repository.load_many(user_id=user_id, ids=page_ids)

        items = [
            self._build_row(
                announcement,
                stats.get(announcement.id, []),
                marks.get(announcement.id),
            )
            for announcement in announcements
        ]
        page_count = max(1, (total + query.page_size - 1) // query.page_size)
        return JobCatalogList(
            items=items,
            page=query.page,
            page_size=query.page_size,
            total=total,
            page_count=page_count,
        )

    def get_announcement(self, *, user_id: str, announcement_id: str) -> JobAnnouncementDetail:
        announcement = self.repository.get(user_id=user_id, announcement_id=announcement_id)
        if announcement is None:
            raise AppError(
                code="JOB_NOT_FOUND",
                message="职位公告不存在或已被删除",
                status_code=404,
                details={"announcement_id": announcement_id},
            )
        applications = self.repository.application_stats(
            user_id=user_id, announcement_ids=[announcement_id]
        ).get(announcement_id, [])
        by_position = {item.position_id: item for item in applications if item.position_id}
        mark = self.repository.mark_for(user_id=user_id, announcement_id=announcement_id)
        row_status = self._row_status(applications, mark)

        positions = [
            JobPositionRead(
                id=position.id,
                title=position.title,
                category=position.category,
                city=position.city,
                education=position.education,
                headcount=position.headcount,
                jd_text=position.jd_text,
                sort_order=position.sort_order,
                application_id=by_position[position.id].id if position.id in by_position else None,
                application_status=(
                    by_position[position.id].status if position.id in by_position else None
                ),
                application_status_label=(
                    status_label(by_position[position.id].status)
                    if position.id in by_position
                    else None
                ),
            )
            for position in announcement.positions
        ]

        return JobAnnouncementDetail(
            id=announcement.id,
            title=announcement.title,
            company=self._company(announcement.company),
            recruitment_type=announcement.recruitment_type,
            target_cohort=announcement.target_cohort,
            locations=list(announcement.locations or []),
            positions_text=announcement.positions_text,
            announcement_url=announcement.announcement_url,
            source_url=announcement.source_url,
            source_channel=announcement.source_channel,
            published_at=announcement.published_at,
            deadline=self._deadline(announcement),
            raw_text=announcement.raw_text,
            apply_method=dict(announcement.apply_method or {}),
            snapshot_at=announcement.snapshot_at,
            status=getattr(announcement.status, "value", str(announcement.status)),
            visibility=getattr(announcement.visibility, "value", str(announcement.visibility)),
            mark_status=row_status,
            mark_status_label=status_label(row_status),
            mark_note=mark.note if mark else None,
            positions=positions,
            source=self._source(announcement),
            created_at=announcement.created_at,
            updated_at=announcement.updated_at,
        )

    # -- marks -----------------------------------------------------------
    def set_mark(
        self, *, user_id: str, announcement_id: str, payload: JobMarkUpdate
    ) -> JobMarkRead:
        announcement = self.repository.get(user_id=user_id, announcement_id=announcement_id)
        if announcement is None:
            raise AppError(
                code="JOB_NOT_FOUND",
                message="职位公告不存在或已被删除",
                status_code=404,
                details={"announcement_id": announcement_id},
            )
        mark = self.repository.mark_for(user_id=user_id, announcement_id=announcement_id)
        if payload.status == "none":
            if mark is not None:
                self.session.delete(mark)
                self.session.commit()
            return JobMarkRead(
                announcement_id=announcement_id,
                mark_status="not_applied",
                mark_status_label=status_label("not_applied"),
                note=None,
            )

        if mark is None:
            mark = UserJobMark(
                user_id=user_id,
                announcement_id=announcement_id,
                status="deferred",
                note=payload.note,
            )
            self.session.add(mark)
        else:
            mark.status = "deferred"
            mark.note = payload.note
        self.session.commit()

        applications = self.repository.application_stats(
            user_id=user_id, announcement_ids=[announcement_id]
        ).get(announcement_id, [])
        row_status = self._row_status(applications, mark)
        return JobMarkRead(
            announcement_id=announcement_id,
            mark_status=row_status,
            mark_status_label=status_label(row_status),
            note=mark.note,
        )

    def set_marks(
        self, *, user_id: str, payload: JobMarkBatch
    ) -> list[JobMarkRead]:
        """Batch defer / restore. Validates ownership first, then commits once."""

        announcement_ids = list(dict.fromkeys(payload.announcement_ids))
        announcements = self.repository.load_many(user_id=user_id, ids=announcement_ids)
        if len(announcements) != len(announcement_ids):
            raise AppError(
                code="JOB_NOT_FOUND",
                message="部分职位公告不存在或无权访问",
                status_code=404,
                details={"announcement_ids": announcement_ids},
            )
        marks = self.repository.marks(user_id=user_id, announcement_ids=announcement_ids)
        for announcement_id in announcement_ids:
            mark = marks.get(announcement_id)
            if payload.status == "none":
                if mark is not None:
                    self.session.delete(mark)
            elif mark is None:
                self.session.add(
                    UserJobMark(
                        user_id=user_id,
                        announcement_id=announcement_id,
                        status="deferred",
                        note=payload.note,
                    )
                )
            else:
                mark.status = "deferred"
                mark.note = payload.note
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

        stats = self.repository.application_stats(
            user_id=user_id, announcement_ids=announcement_ids
        )
        fresh_marks = self.repository.marks(user_id=user_id, announcement_ids=announcement_ids)
        results: list[JobMarkRead] = []
        for announcement_id in announcement_ids:
            mark = fresh_marks.get(announcement_id)
            row_status = self._row_status(stats.get(announcement_id, []), mark)
            results.append(
                JobMarkRead(
                    announcement_id=announcement_id,
                    mark_status=row_status,
                    mark_status_label=status_label(row_status),
                    note=mark.note if mark is not None else None,
                )
            )
        return results

    # -- facets ----------------------------------------------------------
    def facets(self, *, user_id: str) -> JobFacets:
        company_types = self.repository.distinct_company_types(user_id=user_id)
        recruitment_types = self.repository.distinct_announcement_values(
            user_id=user_id, column=JobAnnouncement.recruitment_type
        )
        cohorts = self.repository.distinct_announcement_values(
            user_id=user_id, column=JobAnnouncement.target_cohort
        )
        locations = self.repository.distinct_locations(user_id=user_id)
        categories = self.repository.distinct_categories(user_id=user_id)

        status_counts = self.repository.status_counts(user_id=user_id)

        return JobFacets(
            company_types=_options(COMPANY_TYPES, company_types),
            recruitment_types=_options(RECRUITMENT_TYPES, recruitment_types),
            target_cohorts=_options([], cohorts, include_extra=True),
            locations=_options([], locations, include_extra=True),
            job_categories=_options([], categories, include_extra=True),
            statuses=_options(FILTERABLE_STATUSES, status_counts),
        )

    # -- import pipeline -------------------------------------------------
    def start_text_import(
        self,
        *,
        user_id: str,
        raw_text: str,
        source_name: str | None,
        source_url: str | None,
        ai_config: AiConfig | None = None,
    ) -> JobImportRead:
        return self._create_import(
            user_id=user_id,
            mode="text",
            raw_text=raw_text,
            source_name=source_name,
            source_url=source_url,
            ai_config=ai_config,
        )

    def start_file_import(
        self,
        *,
        user_id: str,
        file_name: str,
        content: bytes,
        ai_config: AiConfig | None = None,
    ) -> JobImportRead:
        text, _content_type = extract_text_from_upload(file_name=file_name, content=content)
        return self._create_import(
            user_id=user_id,
            mode="file",
            raw_text=text,
            source_name=file_name,
            source_url=None,
            ai_config=ai_config,
        )

    def start_article_import(
        self,
        *,
        user_id: str,
        url: str,
        source_name: str | None,
        ai_config: AiConfig | None = None,
    ) -> JobImportRead:
        snapshot = fetch_article(url)
        return self._create_import(
            user_id=user_id,
            mode="article_url",
            raw_text=snapshot.text,
            source_name=source_name or snapshot.account_name,
            source_url=url,
            fallback_title=snapshot.title,
            published_at=snapshot.published_at,
            ai_config=ai_config,
        )

    def list_imports(self, *, user_id: str) -> JobImportList:
        rows = self.repository.list_imports(user_id=user_id)
        return JobImportList(
            items=[JobImportRead.model_validate(row) for row in rows], total=len(rows)
        )

    def confirm_import(
        self, *, user_id: str, import_id: str, payload: JobImportConfirm
    ) -> JobAnnouncementDetail:
        row = self.repository.get_import(user_id=user_id, import_id=import_id)
        if row is None:
            raise AppError(
                code="JOB_IMPORT_NOT_FOUND",
                message="导入记录不存在或已被删除",
                status_code=404,
                details={"import_id": import_id},
            )

        dedupe_key = _dedupe_key(
            user_id=user_id,
            company_name=payload.company_name,
            title=payload.title,
            cohort=payload.target_cohort,
            url=str(payload.announcement_url) if payload.announcement_url else row.source_url,
        )
        existing = self.repository.find_by_dedupe(dedupe_key=dedupe_key)
        if existing is not None:
            raise AppError(
                code="JOB_ANNOUNCEMENT_EXISTS",
                message="这条招聘公告已经导入过",
                status_code=409,
                details={"announcement_id": existing.id},
            )

        company = self.repository.company_by_name(name=payload.company_name)
        if company is None:
            company = Company(name=payload.company_name)
            self.session.add(company)
        if payload.company_type:
            company.company_type = payload.company_type
        if payload.company_scale:
            company.company_scale = payload.company_scale
        if payload.industry:
            company.industry = payload.industry
        self.session.flush()

        source = self._source_for(
            user_id=user_id,
            mode=row.mode,
            source_name=_source_name(row),
            source_url=row.source_url,
        )

        announcement = JobAnnouncement(
            company_id=company.id,
            source_id=source.id if source else None,
            title=payload.title,
            recruitment_type=payload.recruitment_type,
            target_cohort=payload.target_cohort,
            locations=payload.locations,
            locations_text="、".join(payload.locations) or None,
            positions_text=positions_text([item.title for item in payload.positions])
            or positions_text([str(item) for item in (row.parsed.get("positions") or [])]),
            announcement_url=str(payload.announcement_url) if payload.announcement_url else None,
            source_url=row.source_url,
            source_channel=_source_channel(row.mode),
            published_at=_as_datetime(payload.published_at),
            deadline_at=_as_datetime(payload.deadline_at),
            deadline_text=payload.deadline_text,
            raw_text=(payload.raw_text or row.raw_snapshot or "")[:MAX_RAW_TEXT],
            apply_method=payload.apply_method or row.parsed.get("apply_method") or {},
            snapshot_at=datetime.now(timezone.utc),
            visibility="private",
            owner_user_id=user_id,
            dedupe_key=dedupe_key,
        )
        self.session.add(announcement)
        self.session.flush()

        for index, item in enumerate(payload.positions):
            self.session.add(
                JobPosition(
                    announcement_id=announcement.id,
                    title=item.title,
                    category=item.category,
                    city=item.city,
                    education=item.education,
                    headcount=item.headcount,
                    jd_text=item.jd_text,
                    sort_order=index,
                )
            )

        row.status = "confirmed"
        row.parsed = {
            **(row.parsed or {}),
            **payload.model_dump(mode="json"),
            "announcement_id": announcement.id,
        }
        self.session.commit()

        return self.get_announcement(user_id=user_id, announcement_id=announcement.id)

    def delete_import(self, *, user_id: str, import_id: str) -> None:
        row = self.repository.get_import(user_id=user_id, import_id=import_id)
        if row is None:
            raise AppError(
                code="JOB_IMPORT_NOT_FOUND",
                message="导入记录不存在或已被删除",
                status_code=404,
                details={"import_id": import_id},
            )
        self.session.delete(row)
        self.session.commit()

    # -- table preferences -----------------------------------------------
    def get_table_preference(self, *, user_id: str) -> JobTablePreference:
        preference = self.repository.get_preference(user_id=user_id, table_key=JOB_TABLE_KEY)
        visible = (
            list(preference.visible_columns)
            if preference and preference.visible_columns
            else list(DEFAULT_VISIBLE_COLUMNS)
        )
        return JobTablePreference(
            table_key=JOB_TABLE_KEY,
            visible_columns=visible,
            available_columns=[
                ColumnOption(
                    key=key,
                    label=COLUMN_LABELS[key],
                    default=key in DEFAULT_VISIBLE_COLUMNS,
                )
                for key in TABLE_COLUMNS
            ],
        )

    def save_table_preference(
        self, *, user_id: str, visible_columns: list[str]
    ) -> JobTablePreference:
        ordered = [key for key in TABLE_COLUMNS if key in set(visible_columns)]
        self.repository.save_preference(
            user_id=user_id, table_key=JOB_TABLE_KEY, visible_columns=ordered
        )
        return self.get_table_preference(user_id=user_id)

    # -- export ----------------------------------------------------------
    def export_csv(self, *, user_id: str, query: JobCatalogQuery) -> str:
        query = query.model_copy(update={"page": 1, "page_size": 10_000})
        catalog = self.list_catalog(user_id=user_id, query=query)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "公司名称",
                "公司类型",
                "公司规模",
                "招聘类型",
                "招聘对象",
                "工作地点",
                "岗位",
                "更新时间",
                "投递截止",
                "状态",
                "来源",
                "公告链接",
            ]
        )
        for row in catalog.items:
            writer.writerow(
                [
                    row.company.name,
                    row.company.type or "",
                    row.company.scale or "",
                    row.recruitment_type or "",
                    row.target_cohort or "",
                    "、".join(row.locations),
                    row.positions_preview,
                    row.updated_at.date().isoformat(),
                    row.deadline.text or "",
                    row.mark_status_label,
                    row.source.name or "",
                    row.source.url or "",
                ]
            )
        return buffer.getvalue()

    # -- helpers ---------------------------------------------------------
    def _create_import(
        self,
        *,
        user_id: str,
        mode: str,
        raw_text: str,
        source_name: str | None,
        source_url: str | None,
        fallback_title: str | None = None,
        published_at: datetime | None = None,
        ai_config: AiConfig | None = None,
    ) -> JobImportRead:
        text = raw_text.strip()
        if len(text) < 20:
            raise AppError(
                code="JOB_IMPORT_FAILED",
                message="公告正文至少需要 20 个字符",
                status_code=422,
            )
        parsed = parse_announcement(
            text, source_name=source_name, fallback_title=fallback_title
        )
        if published_at and parsed.published_at is None:
            parsed.published_at = published_at

        # Plan §5.3.5: rule result first, LLM only fills the blanks. Any failure
        # keeps the rule output and records llm_used=False.
        payload = {**parsed.as_dict(), "source_name": source_name}
        payload, llm_used = enhance_announcement(payload, text, ai_config)

        row = JobImport(
            user_id=user_id,
            mode=mode,
            source_url=source_url,
            status="parsed_llm" if llm_used else "parsed_rule",
            parsed=payload,
            raw_snapshot=text[:MAX_RAW_TEXT],
            llm_used=llm_used,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return JobImportRead.model_validate(row)

    def _build_row(self, announcement, applications, mark) -> JobRow:
        positions = list(announcement.positions or [])
        titles = [position.title for position in positions]
        preview = "、".join(titles) if titles else (announcement.positions_text or "")
        if len(preview) > PREVIEW_LIMIT:
            preview = preview[:PREVIEW_LIMIT] + "…"

        row_status = self._row_status(applications, mark)
        stage_summary: dict[str, int] = {}
        for application in applications:
            label = status_label(application.status)
            stage_summary[label] = stage_summary.get(label, 0) + 1
        applied_positions = {item.position_id for item in applications if item.position_id}

        return JobRow(
            id=announcement.id,
            title=announcement.title,
            company=self._company(announcement.company),
            recruitment_type=announcement.recruitment_type,
            target_cohort=announcement.target_cohort,
            locations=list(announcement.locations or []),
            positions_preview=preview,
            position_count=len(positions) or (1 if announcement.positions_text else 0),
            published_at=announcement.published_at.date() if announcement.published_at else None,
            updated_at=announcement.updated_at,
            deadline=self._deadline(announcement),
            mark_status=row_status,
            mark_status_label=status_label(row_status),
            mark_note=mark.note if mark else None,
            stage_summary=stage_summary,
            application_ids=[item.id for item in applications],
            applied_position_count=len(applied_positions),
            source=self._source(announcement),
        )

    @staticmethod
    def _row_status(applications, mark) -> str:
        deferred = mark is not None and mark.status == "deferred"
        return derive_row_status([item.status for item in applications], deferred=deferred)

    @staticmethod
    def _company(company: Company) -> JobRowCompany:
        return JobRowCompany(
            name=company.name,
            type=company.company_type,
            scale=company.company_scale,
            industry=company.industry,
        )

    @staticmethod
    def _deadline(announcement: JobAnnouncement) -> DeadlineInfo:
        text = announcement.deadline_text
        at = announcement.deadline_at.date() if announcement.deadline_at else None
        if not text and at:
            text = at.isoformat()
        return DeadlineInfo(text=text, at=at)

    @staticmethod
    def _source(announcement: JobAnnouncement) -> JobSourceInfo:
        source = announcement.source
        return JobSourceInfo(
            kind=announcement.source_channel,
            name=source.name if source else None,
            url=announcement.source_url or announcement.announcement_url,
        )

    def _source_for(
        self, *, user_id: str, mode: str, source_name: str | None, source_url: str | None
    ) -> AnnouncementSource | None:
        if mode != "article_url":
            return None
        name = (source_name or "公众号").strip()[:200]
        existing = self.session.scalar(
            select(AnnouncementSource).where(
                AnnouncementSource.owner_user_id == user_id,
                AnnouncementSource.name == name,
            )
        )
        if existing is not None:
            existing.last_checked_at = datetime.now(timezone.utc)
            return existing
        source = AnnouncementSource(
            name=name,
            adapter_key="wechat_article",
            home_url=source_url,
            last_checked_at=datetime.now(timezone.utc),
            owner_user_id=user_id,
        )
        self.session.add(source)
        self.session.flush()
        return source


def _options(
    known: tuple[str, ...] | list[str],
    counts: dict[str, int],
    *,
    include_extra: bool = False,
) -> list[FacetOption]:
    values = list(known)
    if include_extra:
        extras = [value for value in counts if value not in values]
        values.extend(sorted(extras, key=lambda item: (-counts[item], item)))
    return [
        FacetOption(value=value, label=status_label(value) if value in _STATUS_LIKE else value, count=counts.get(value, 0))
        for value in values
    ]


_STATUS_LIKE = set(FILTERABLE_STATUSES)


def _dedupe_key(
    *,
    user_id: str,
    company_name: str,
    title: str,
    cohort: str | None,
    url: str | None,
) -> str:
    base = f"url:{url}" if url else f"{company_name}|{title}|{cohort or ''}"
    digest = hashlib.sha256(f"{user_id}:{base}".encode()).hexdigest()
    return digest[:40]


def _as_datetime(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _source_name(row: JobImport) -> str | None:
    parsed = row.parsed or {}
    name = parsed.get("source_name") or parsed.get("company_name")
    return str(name) if name else None


def _source_channel(mode: str) -> str:
    return {"article_url": "wechat_article", "file": "file", "text": "manual"}.get(mode, "manual")
