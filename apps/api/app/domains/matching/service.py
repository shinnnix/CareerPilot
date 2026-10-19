from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import AppError, DocumentNotFoundError, JobNotFoundError
from app.domains.documents.model import DocumentType
from app.domains.documents.repository import DocumentRepository
from app.domains.documents.schemas import ExtractedDocumentData
from app.domains.jobs.repository import JobRepository
from app.domains.matching.schemas import (
    HardGateResult,
    MatchReport,
    ScoreBreakdown,
)
from app.domains.matching.skills import normalize_skills
from app.domains.retrieval.schemas import RetrievalMode, SearchRequest
from app.domains.retrieval.service import RetrievalService

SCORING_VERSION = "explainable-match-v1"


class MatchingService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.jobs = JobRepository(session)
        self.documents = DocumentRepository(session)
        self.retrieval = RetrievalService(session)

    def build_report(self, *, user_id: str, job_id: str, resume_document_id: str) -> MatchReport:
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
                message="匹配报告必须选择简历类型文档",
                status_code=422,
            )

        profile = ExtractedDocumentData.model_validate(resume.extracted_data)
        gate = self._hard_gate(job, profile)
        profile_skills = normalize_skills(profile.skills)
        required = normalize_skills(job.required_skills)
        preferred = normalize_skills(job.preferred_skills)
        matched_required = sorted(required & profile_skills)
        matched_preferred = sorted(preferred & profile_skills)
        required_coverage = len(matched_required) / len(required) if required else 1.0
        preferred_coverage = len(matched_preferred) / len(preferred) if preferred else 1.0

        search = self.retrieval.search(
            user_id=user_id,
            payload=SearchRequest(
                query=job.raw_text,
                mode=RetrievalMode.rerank,
                document_id=resume.id,
                top_k=3,
                candidate_k=20,
                expand_parent=True,
            ),
        )
        semantic = max(
            (
                hit.rerank_score
                if hit.rerank_score is not None
                else max(hit.dense_score or 0, hit.keyword_score or 0)
                for hit in search.items
            ),
            default=0.0,
        )
        semantic = min(max(semantic, 0.0), 1.0)
        domain_score = min(
            len((required | preferred) & profile_skills) / max(len(required | preferred), 1),
            1.0,
        )
        preference_score = 1.0 if gate.checks.get("city", True) else 0.0
        created_at = job.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age_days = max((datetime.now(timezone.utc) - created_at).days, 0)
        freshness_score = 1.0 if age_days <= 30 else 0.7 if age_days <= 90 else 0.4
        breakdown = ScoreBreakdown(
            required_skill_coverage=round(required_coverage, 4),
            preferred_skill_coverage=round(preferred_coverage, 4),
            experience_semantic_score=round(semantic, 4),
            project_domain_score=round(domain_score, 4),
            preference_score=preference_score,
            freshness_score=freshness_score,
        )
        weighted = (
            0.35 * required_coverage
            + 0.20 * preferred_coverage
            + 0.20 * semantic
            + 0.10 * domain_score
            + 0.10 * preference_score
            + 0.05 * freshness_score
        )
        return MatchReport(
            job_id=job.id,
            resume_document_id=resume.id,
            eligible=gate.passed,
            total_score=round(weighted * 100, 2) if gate.passed else 0.0,
            hard_gate=gate,
            breakdown=breakdown,
            matched_required_skills=matched_required,
            missing_required_skills=sorted(required - profile_skills),
            matched_preferred_skills=matched_preferred,
            missing_preferred_skills=sorted(preferred - profile_skills),
            evidence=search.items,
            scoring_version=SCORING_VERSION,
        )

    @staticmethod
    def _hard_gate(job, profile: ExtractedDocumentData) -> HardGateResult:
        checks: dict[str, bool] = {}
        reasons: list[str] = []
        unknowns: list[str] = []
        desired_cities = {city.strip().lower() for city in profile.desired_cities}
        checks["city"] = not desired_cities or not job.city or job.city.lower() in desired_cities
        if not checks["city"]:
            reasons.append(f"职位城市 {job.city} 不在简历期望城市中")
        if job.city and not desired_cities:
            unknowns.append("简历未填写期望城市")
        checks["days_per_week"] = (
            job.internship_days_per_week is None
            or profile.available_days_per_week is None
            or profile.available_days_per_week >= job.internship_days_per_week
        )
        if not checks["days_per_week"]:
            reasons.append("每周可到岗天数低于职位要求")
        if job.internship_days_per_week and profile.available_days_per_week is None:
            unknowns.append("简历未填写每周可到岗天数")
        checks["months"] = (
            job.internship_months is None
            or profile.available_months is None
            or profile.available_months >= job.internship_months
        )
        if not checks["months"]:
            reasons.append("可实习月数短于职位要求")
        if job.internship_months and profile.available_months is None:
            unknowns.append("简历未填写可实习月数")
        return HardGateResult(
            passed=all(checks.values()), checks=checks, reasons=reasons, unknowns=unknowns
        )
