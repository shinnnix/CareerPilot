from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, case, exists, func, literal, or_, select
from sqlalchemy.orm import Session, selectinload

from app.domains.applications.model import Application
from app.domains.jobs.constants import (
    DEFERRED_BUCKET,
    NO_APPLICATION_BUCKET,
    ROW_STATUS_PRIORITY,
    STATUS_RANK,
)
from app.domains.jobs.model import (
    Company,
    Job,
    JobAnnouncement,
    JobImport,
    JobPosition,
    JobStatus,
    UserJobMark,
    UserTablePreference,
)
from app.domains.jobs.schemas import JobCatalogQuery


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(
        self,
        *,
        user_id: str,
        keyword: str | None,
        city: str | None,
        status: JobStatus | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Job], int]:
        filters = [Job.user_id == user_id]
        if keyword:
            pattern = f"%{keyword.strip()}%"
            filters.append(
                or_(
                    Job.title.ilike(pattern),
                    Job.company_name.ilike(pattern),
                    Job.raw_text.ilike(pattern),
                )
            )
        if city:
            filters.append(Job.city == city.strip())
        if status:
            filters.append(Job.status == status)

        total = self.session.scalar(select(func.count()).select_from(Job).where(*filters)) or 0
        statement = (
            select(Job)
            .where(*filters)
            .order_by(Job.created_at.desc(), Job.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.session.scalars(statement)), total

    def get(self, *, user_id: str, job_id: str) -> Job | None:
        return self.session.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))

    def add(self, job: Job) -> Job:
        self.session.add(job)
        self.session.flush()
        self.session.refresh(job)
        return job

    def delete(self, job: Job) -> None:
        self.session.delete(job)
        self.session.flush()


@dataclass(frozen=True)
class ApplicationBrief:
    id: str
    position_id: str | None
    status: str


class JobCatalogRepository:
    """Catalog queries: announcement rows + their application/mark aggregates."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- filters ---------------------------------------------------------
    @staticmethod
    def _rank_expression():
        """Funnel rank of one application status; lower = further along."""

        return case(
            {status: rank for status, rank in STATUS_RANK.items()},
            value=Application.status,
            else_=99,
        )

    def _best_rank(self, *, user_id: str):
        """Correlated scalar: the furthest rank among an announcement's rows."""

        rank = self._rank_expression()
        return (
            select(func.min(rank))
            .where(
                Application.announcement_id == JobAnnouncement.id,
                Application.user_id == user_id,
                Application.deleted_at.is_(None),
            )
            .scalar_subquery()
        )

    def _has_application(self, *, user_id: str):
        return exists(
            select(literal(1)).where(
                Application.announcement_id == JobAnnouncement.id,
                Application.user_id == user_id,
                Application.deleted_at.is_(None),
            )
        )

    def _is_deferred(self, *, user_id: str):
        return exists(
            select(literal(1)).where(
                UserJobMark.announcement_id == JobAnnouncement.id,
                UserJobMark.user_id == user_id,
                UserJobMark.status == "deferred",
            )
        )

    def _status_condition(self, *, user_id: str, status: str):
        """Push the derived row status into SQL (plan §2.6).

        ``deferred`` / ``not_applied`` depend on the *absence* of applications
        plus the user mark; every other status compares the announcement's best
        rank, so the filter runs before pagination instead of after it.
        """

        if status == "deferred":
            return and_(~self._has_application(user_id=user_id), self._is_deferred(user_id=user_id))
        if status == "not_applied":
            return and_(
                ~self._has_application(user_id=user_id),
                ~self._is_deferred(user_id=user_id),
            )
        return self._best_rank(user_id=user_id) == STATUS_RANK[status]

    def _conditions(self, *, user_id: str, query: JobCatalogQuery) -> list:
        conditions = [JobAnnouncement.owner_user_id == user_id]
        if query.keyword:
            pattern = f"%{query.keyword.strip()}%"
            conditions.append(
                or_(
                    JobAnnouncement.title.ilike(pattern),
                    Company.name.ilike(pattern),
                    JobAnnouncement.positions_text.ilike(pattern),
                    JobAnnouncement.raw_text.ilike(pattern),
                )
            )
        if query.company:
            conditions.append(Company.name.ilike(f"%{query.company.strip()}%"))
        if query.company_type:
            conditions.append(Company.company_type == query.company_type)
        if query.recruitment_type:
            conditions.append(JobAnnouncement.recruitment_type == query.recruitment_type)
        if query.target_cohort:
            conditions.append(JobAnnouncement.target_cohort == query.target_cohort)
        if query.location:
            conditions.append(
                JobAnnouncement.locations_text.ilike(f"%{query.location.strip()}%")
            )
        if query.job_category:
            conditions.append(
                select(JobPosition.id)
                .where(
                    JobPosition.announcement_id == JobAnnouncement.id,
                    JobPosition.category == query.job_category,
                )
                .exists()
            )
        if query.status:
            conditions.append(self._status_condition(user_id=user_id, status=query.status))
        return conditions

    def _order(self, query: JobCatalogQuery) -> list:
        if query.sort == "published_desc":
            return [JobAnnouncement.published_at.desc().nulls_last(), JobAnnouncement.id]
        if query.sort == "deadline_asc":
            return [JobAnnouncement.deadline_at.asc().nulls_last(), JobAnnouncement.id]
        return [JobAnnouncement.updated_at.desc(), JobAnnouncement.id]

    def page(self, *, user_id: str, query: JobCatalogQuery) -> tuple[list[str], int]:
        """One page of announcement ids plus the filtered total, both from SQL."""

        conditions = self._conditions(user_id=user_id, query=query)
        base = (
            select(JobAnnouncement.id)
            .join(Company, Company.id == JobAnnouncement.company_id)
            .where(*conditions)
        )
        total = int(self.session.scalar(select(func.count()).select_from(base.subquery())) or 0)
        statement = (
            base.order_by(*self._order(query))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
        return [str(value) for value in self.session.scalars(statement)], total

    def status_counts(self, *, user_id: str) -> dict[str, int]:
        """Derived-status facet counts, computed with one grouped SQL query."""

        rank = self._rank_expression()
        best = (
            select(
                Application.announcement_id.label("aid"),
                func.min(rank).label("best"),
            )
            .where(
                Application.user_id == user_id,
                Application.announcement_id.is_not(None),
                Application.deleted_at.is_(None),
            )
            .group_by(Application.announcement_id)
            .subquery()
        )
        mark_flag = case((UserJobMark.id.is_not(None), 1), else_=0)
        bucket = case(
            (best.c.best.is_(None), literal(NO_APPLICATION_BUCKET) + mark_flag),
            else_=best.c.best,
        )
        statement = (
            select(bucket.label("bucket"), func.count())
            .select_from(JobAnnouncement)
            .outerjoin(best, best.c.aid == JobAnnouncement.id)
            .outerjoin(
                UserJobMark,
                and_(
                    UserJobMark.announcement_id == JobAnnouncement.id,
                    UserJobMark.user_id == user_id,
                ),
            )
            .where(JobAnnouncement.owner_user_id == user_id)
            .group_by(bucket)
        )
        counts = {status: 0 for status in ROW_STATUS_PRIORITY}
        counts["deferred"] = 0
        for value, count in self.session.execute(statement):
            bucket_value = int(value)
            if bucket_value == NO_APPLICATION_BUCKET:
                counts["not_applied"] += int(count)
            elif bucket_value == DEFERRED_BUCKET:
                counts["deferred"] += int(count)
            elif 0 <= bucket_value < len(ROW_STATUS_PRIORITY):
                counts[ROW_STATUS_PRIORITY[bucket_value]] += int(count)
        return counts

    def load_many(self, *, user_id: str, ids: list[str]) -> list[JobAnnouncement]:
        if not ids:
            return []
        statement = (
            select(JobAnnouncement)
            .where(JobAnnouncement.id.in_(ids), JobAnnouncement.owner_user_id == user_id)
            .options(selectinload(JobAnnouncement.positions))
        )
        rows = list(self.session.scalars(statement))
        order = {value: index for index, value in enumerate(ids)}
        rows.sort(key=lambda row: order.get(row.id, 0))
        return rows

    def get(self, *, user_id: str, announcement_id: str) -> JobAnnouncement | None:
        statement = (
            select(JobAnnouncement)
            .where(
                JobAnnouncement.id == announcement_id,
                JobAnnouncement.owner_user_id == user_id,
            )
            .options(selectinload(JobAnnouncement.positions))
        )
        return self.session.scalar(statement)

    def application_stats(
        self, *, user_id: str, announcement_ids: list[str]
    ) -> dict[str, list[ApplicationBrief]]:
        if not announcement_ids:
            return {}
        statement = select(
            Application.id,
            Application.announcement_id,
            Application.position_id,
            Application.status,
        ).where(
            Application.user_id == user_id,
            Application.announcement_id.in_(announcement_ids),
            Application.deleted_at.is_(None),
        )
        result: dict[str, list[ApplicationBrief]] = {}
        for application_id, announcement_id, position_id, status in self.session.execute(
            statement
        ):
            result.setdefault(str(announcement_id), []).append(
                ApplicationBrief(
                    id=application_id,
                    position_id=position_id,
                    status=getattr(status, "value", str(status)),
                )
            )
        return result

    def marks(
        self, *, user_id: str, announcement_ids: list[str]
    ) -> dict[str, UserJobMark]:
        if not announcement_ids:
            return {}
        statement = select(UserJobMark).where(
            UserJobMark.user_id == user_id,
            UserJobMark.announcement_id.in_(announcement_ids),
        )
        return {mark.announcement_id: mark for mark in self.session.scalars(statement)}

    def mark_for(self, *, user_id: str, announcement_id: str) -> UserJobMark | None:
        return self.session.scalar(
            select(UserJobMark).where(
                UserJobMark.user_id == user_id,
                UserJobMark.announcement_id == announcement_id,
            )
        )

    def positions_by_announcement(
        self, *, announcement_ids: list[str]
    ) -> dict[str, list[JobPosition]]:
        if not announcement_ids:
            return {}
        statement = select(JobPosition).where(JobPosition.announcement_id.in_(announcement_ids))
        result: dict[str, list[JobPosition]] = {}
        for position in self.session.scalars(statement):
            result.setdefault(position.announcement_id, []).append(position)
        return result

    def position_map(self, *, announcement_id: str) -> dict[str, JobPosition]:
        statement = select(JobPosition).where(JobPosition.announcement_id == announcement_id)
        return {position.id: position for position in self.session.scalars(statement)}

    # -- facets ----------------------------------------------------------
    def distinct_company_types(self, *, user_id: str) -> dict[str, int]:
        statement = (
            select(Company.company_type, func.count())
            .join(JobAnnouncement, JobAnnouncement.company_id == Company.id)
            .where(
                JobAnnouncement.owner_user_id == user_id,
                Company.company_type.is_not(None),
            )
            .group_by(Company.company_type)
        )
        return {str(key): int(count) for key, count in self.session.execute(statement)}

    def distinct_announcement_values(self, *, user_id: str, column) -> dict[str, int]:
        statement = (
            select(column, func.count())
            .where(JobAnnouncement.owner_user_id == user_id, column.is_not(None))
            .group_by(column)
        )
        return {str(key): int(count) for key, count in self.session.execute(statement)}

    def distinct_locations(self, *, user_id: str) -> dict[str, int]:
        statement = select(JobAnnouncement.locations).where(
            JobAnnouncement.owner_user_id == user_id
        )
        counts: dict[str, int] = {}
        for locations in self.session.scalars(statement):
            for location in locations or []:
                counts[str(location)] = counts.get(str(location), 0) + 1
        return counts

    def distinct_categories(self, *, user_id: str) -> dict[str, int]:
        statement = (
            select(JobPosition.category, func.count())
            .join(JobAnnouncement, JobAnnouncement.id == JobPosition.announcement_id)
            .where(
                JobAnnouncement.owner_user_id == user_id,
                JobPosition.category.is_not(None),
            )
            .group_by(JobPosition.category)
        )
        return {str(key): int(count) for key, count in self.session.execute(statement)}

    # -- companies / imports / preferences -------------------------------
    def company_by_name(self, *, name: str) -> Company | None:
        return self.session.scalar(select(Company).where(Company.name == name))

    def add(self, instance):
        self.session.add(instance)
        self.session.flush()
        return instance

    def get_import(self, *, user_id: str, import_id: str) -> JobImport | None:
        return self.session.scalar(
            select(JobImport).where(JobImport.id == import_id, JobImport.user_id == user_id)
        )

    def list_imports(self, *, user_id: str, limit: int = 50) -> list[JobImport]:
        statement = (
            select(JobImport)
            .where(JobImport.user_id == user_id)
            .order_by(JobImport.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def get_preference(self, *, user_id: str, table_key: str) -> UserTablePreference | None:
        return self.session.scalar(
            select(UserTablePreference).where(
                UserTablePreference.user_id == user_id,
                UserTablePreference.table_key == table_key,
            )
        )

    def save_preference(
        self, *, user_id: str, table_key: str, visible_columns: list[str]
    ) -> UserTablePreference:
        preference = self.get_preference(user_id=user_id, table_key=table_key)
        if preference is None:
            preference = UserTablePreference(
                user_id=user_id, table_key=table_key, visible_columns=visible_columns
            )
            self.session.add(preference)
        else:
            preference.visible_columns = visible_columns
        self.session.commit()
        self.session.refresh(preference)
        return preference

    def find_by_dedupe(self, *, dedupe_key: str) -> JobAnnouncement | None:
        return self.session.scalar(
            select(JobAnnouncement).where(JobAnnouncement.dedupe_key == dedupe_key)
        )

    def count_announcements(self, *, user_id: str) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(JobAnnouncement)
                .where(JobAnnouncement.owner_user_id == user_id)
            )
            or 0
        )

    def purge_imports(self, *, user_id: str, before: datetime) -> None:
        for row in self.session.scalars(
            select(JobImport).where(
                JobImport.user_id == user_id,
                JobImport.created_at < before,
            )
        ):
            self.session.delete(row)
        self.session.commit()
