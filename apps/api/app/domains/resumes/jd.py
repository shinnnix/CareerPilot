"""Resolve the target job description an optimization run is measured against.

A JD can come from a tracked job, an imported JD document, or inline pasted text.
All three paths produce the same normalized profile so the scoring code stays
independent from where the requirement text came from.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.core.errors import AppError, DocumentNotFoundError, JobNotFoundError
from app.domains.documents.model import DocumentType
from app.domains.documents.parser import normalize_text, split_sections
from app.domains.documents.repository import DocumentRepository
from app.domains.documents.schemas import ExtractedDocumentData
from app.domains.jobs.model import Job
from app.domains.jobs.repository import JobCatalogRepository, JobRepository
from app.domains.matching.skills import detect_skills, normalize_skills
from app.domains.resumes.schemas import JdSnapshot, ResumeOptimizeRequest

REQUIREMENT_TITLES = {"任职要求", "岗位要求", "职位要求", "基本要求", "任职资格", "能力要求"}
PREFERRED_TITLES = {"加分项", "优先条件", "加分", "优先录用条件", "加分技能"}


@dataclass(frozen=True)
class JdProfile:
    source: Literal["job", "document", "text", "announcement"]
    title: str
    company_name: str | None
    city: str | None
    raw_text: str
    required_skills: list[str]
    preferred_skills: list[str]
    internship_days_per_week: int | None
    internship_months: int | None
    job_id: str | None
    document_id: str | None
    announcement_id: str | None = None
    published_at: datetime | None = None
    job: Job | None = None
    profile: ExtractedDocumentData | None = None

    def snapshot(self) -> JdSnapshot:
        return JdSnapshot(
            source=self.source,
            job_id=self.job_id,
            announcement_id=self.announcement_id,
            document_id=self.document_id,
            title=self.title[:200] or "目标 JD",
            company_name=self.company_name,
            city=self.city,
            required_skills=self.required_skills,
            preferred_skills=self.preferred_skills,
            internship_days_per_week=self.internship_days_per_week,
            internship_months=self.internship_months,
            raw_text_excerpt=self.raw_text[:2000],
        )


def resolve_jd_profile(
    session: Session, *, user_id: str, payload: ResumeOptimizeRequest
) -> JdProfile:
    if payload.job_id:
        return _from_job(session, user_id=user_id, job_id=payload.job_id)
    if payload.announcement_id:
        return _from_announcement(
            session, user_id=user_id, announcement_id=payload.announcement_id
        )
    if payload.jd_document_id:
        return _from_document(session, user_id=user_id, document_id=payload.jd_document_id)
    if payload.jd_text:
        return _from_text(payload.jd_text)
    raise AppError(
        code="JD_REQUIRED",
        message="请提供目标职位公告、JD 文档或粘贴岗位描述后再生成优化建议",
        status_code=422,
    )


def _from_announcement(session: Session, *, user_id: str, announcement_id: str) -> JdProfile:
    """Module 1 catalog announcement → JD profile (resume ↔ job catalog link)."""

    announcement = JobCatalogRepository(session).get(
        user_id=user_id, announcement_id=announcement_id
    )
    if announcement is None:
        raise JobNotFoundError(announcement_id)

    raw_text = (announcement.raw_text or "").strip()
    if not raw_text:
        raw_text = "\n".join(
            part
            for part in (announcement.title, announcement.positions_text or "")
            if part
        )
    text_required, text_preferred = requirements_from_text(raw_text)
    position_skills: set[str] = set()
    for position in announcement.positions:
        position_skills |= set(
            detect_skills(
                " ".join(
                    part
                    for part in (position.title, position.jd_text or "")
                    if part
                )
            )
        )
    required = set(text_required) | position_skills
    if not required:
        required = set(detect_skills(f"{raw_text}\n{announcement.positions_text or ''}"))
    preferred = set(text_preferred) - required
    return JdProfile(
        source="announcement",
        title=announcement.title,
        company_name=announcement.company.name if announcement.company else None,
        city=announcement.locations[0] if announcement.locations else None,
        raw_text=raw_text,
        required_skills=sorted(required),
        preferred_skills=sorted(preferred),
        internship_days_per_week=None,
        internship_months=None,
        job_id=None,
        document_id=None,
        announcement_id=announcement.id,
        published_at=announcement.published_at,
    )


def _from_job(session: Session, *, user_id: str, job_id: str) -> JdProfile:
    job = JobRepository(session).get(user_id=user_id, job_id=job_id)
    if job is None:
        raise JobNotFoundError(job_id)
    text_required, text_preferred = requirements_from_text(job.raw_text)
    required = normalize_skills(job.required_skills) | set(text_required)
    if not required:
        required = set(detect_skills(job.raw_text))
    preferred = (normalize_skills(job.preferred_skills) | set(text_preferred)) - required
    return JdProfile(
        source="job",
        title=job.title,
        company_name=job.company_name,
        city=job.city,
        raw_text=job.raw_text,
        required_skills=sorted(required),
        preferred_skills=sorted(preferred),
        internship_days_per_week=job.internship_days_per_week,
        internship_months=job.internship_months,
        job_id=job.id,
        document_id=None,
        published_at=job.created_at,
        job=job,
    )


def _from_document(session: Session, *, user_id: str, document_id: str) -> JdProfile:
    document = DocumentRepository(session).get(user_id=user_id, document_id=document_id)
    if document is None:
        raise DocumentNotFoundError(document_id)
    if document.document_type == DocumentType.resume:
        raise AppError(
            code="JD_DOCUMENT_REQUIRED",
            message="目标 JD 需要职位描述类文档，不能使用简历文档",
            status_code=422,
            details={"document_id": document_id},
        )
    profile = ExtractedDocumentData.model_validate(document.extracted_data)
    text_required, text_preferred = requirements_from_text(document.raw_text)
    required = set(text_required) | normalize_skills(profile.skills)
    preferred = set(text_preferred) - required
    title = profile.title or document.display_name
    return JdProfile(
        source="document",
        title=title,
        company_name=profile.company_name,
        city=profile.city,
        raw_text=document.raw_text,
        required_skills=sorted(required),
        preferred_skills=sorted(preferred),
        internship_days_per_week=profile.available_days_per_week,
        internship_months=profile.available_months,
        job_id=None,
        document_id=document.id,
        published_at=document.created_at,
        profile=profile,
    )


def _from_text(raw_text: str) -> JdProfile:
    normalized = normalize_text(raw_text)
    first_line = next((line.strip() for line in normalized.splitlines() if line.strip()), "")
    text_required, text_preferred = requirements_from_text(normalized)
    required = set(text_required) or set(detect_skills(normalized))
    preferred = set(text_preferred) - required
    return JdProfile(
        source="text",
        title=first_line[:200] or "自定义 JD",
        company_name=_labeled_value(normalized, ("公司", "公司名称")),
        city=_labeled_value(normalized, ("城市", "工作地点", "地点")),
        raw_text=normalized,
        required_skills=sorted(required),
        preferred_skills=sorted(preferred),
        internship_days_per_week=None,
        internship_months=None,
        job_id=None,
        document_id=None,
    )


def requirements_from_text(text: str) -> tuple[list[str], list[str]]:
    required: set[str] = set()
    preferred: set[str] = set()
    for section in split_sections(normalize_text(text)):
        normalized_title = re.sub(r"[\s：:]+", "", section.title)
        if normalized_title in REQUIREMENT_TITLES:
            required |= set(detect_skills(section.content))
        elif normalized_title in PREFERRED_TITLES:
            preferred |= set(detect_skills(section.content))
    return sorted(required), sorted(preferred)


def _labeled_value(text: str, labels: tuple[str, ...]) -> str | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"^(?:{label_pattern})\s*[：:]\s*([^\n]{{1,100}})$",
        text,
        flags=re.MULTILINE,
    )
    return match.group(1).strip() if match else None
