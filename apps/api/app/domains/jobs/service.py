from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, JobNotFoundError
from app.domains.applications.model import Application
from app.domains.jobs.model import Job, JobStatus
from app.domains.jobs.repository import JobRepository
from app.domains.jobs.schemas import JobCreate, JobList, JobRead, JobUpdate


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
