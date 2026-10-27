from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.domains.resumes.model import Resume, ResumeOptimization


class ResumeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, *, user_id: str, page: int, page_size: int) -> tuple[list[Resume], int]:
        filters = [Resume.user_id == user_id]
        total = self.session.scalar(select(func.count()).select_from(Resume).where(*filters)) or 0
        statement = (
            select(Resume)
            .where(*filters)
            .order_by(Resume.updated_at.desc(), Resume.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.session.scalars(statement)), total

    def get(self, *, user_id: str, resume_id: str) -> Resume | None:
        return self.session.scalar(
            select(Resume)
            .where(Resume.id == resume_id, Resume.user_id == user_id)
            .options(selectinload(Resume.optimizations))
        )

    def get_by_document(self, *, user_id: str, document_id: str) -> Resume | None:
        return self.session.scalar(
            select(Resume).where(Resume.user_id == user_id, Resume.document_id == document_id)
        )

    def add(self, resume: Resume) -> Resume:
        self.session.add(resume)
        self.session.flush()
        return resume

    def delete(self, resume: Resume) -> None:
        self.session.delete(resume)
        self.session.flush()


class ResumeOptimizationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_resume(self, *, user_id: str, resume_id: str) -> list[ResumeOptimization]:
        statement = (
            select(ResumeOptimization)
            .where(
                ResumeOptimization.user_id == user_id,
                ResumeOptimization.resume_id == resume_id,
            )
            .order_by(ResumeOptimization.created_at.desc(), ResumeOptimization.id)
        )
        return list(self.session.scalars(statement))

    def get(
        self, *, user_id: str, resume_id: str, optimization_id: str
    ) -> ResumeOptimization | None:
        return self.session.scalar(
            select(ResumeOptimization).where(
                ResumeOptimization.id == optimization_id,
                ResumeOptimization.user_id == user_id,
                ResumeOptimization.resume_id == resume_id,
            )
        )

    def add(self, optimization: ResumeOptimization) -> ResumeOptimization:
        self.session.add(optimization)
        self.session.flush()
        return optimization
