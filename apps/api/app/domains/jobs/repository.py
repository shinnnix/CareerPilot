from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.domains.jobs.model import Job, JobStatus


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
