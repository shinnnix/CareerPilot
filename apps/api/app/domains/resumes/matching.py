"""Explainable resume-to-JD scoring that does not require a retrieval index.

The job-centric matching service ranks a resume document against a tracked job with
retrieval evidence. Resume optimization works on the editable resume structure, so
it reuses the same score breakdown contract while deriving every component from the
text the user can actually see and edit.
"""

import re
from datetime import datetime, timezone

from app.domains.documents.schemas import ExtractedDocumentData
from app.domains.matching.gates import evaluate_hard_gate
from app.domains.matching.schemas import HardGateResult, ScoreBreakdown
from app.domains.matching.skills import detect_skills, display_skill, normalize_skills
from app.domains.resumes.jd import JdProfile
from app.domains.resumes.parser import entry_text, resume_corpus
from app.domains.resumes.schemas import (
    ResumeHead,
    ResumeMatchEvidence,
    ResumeMatchReport,
    ResumeSection,
)

SCORING_VERSION = "resume-optimize-v1"
LATIN_TERM = re.compile(r"[a-z][a-z0-9+#.\-]{1,24}")
CJK_RUN = re.compile(r"[\u4e00-\u9fa5]{2,}")
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "you",
    "your",
    "our",
    "team",
    "work",
    "will",
    "are",
    "have",
    "from",
    "that",
    "this",
    "job",
    "role",
    "plus",
    "etc",
    "api",
    "app",
}
STOP_BIGRAMS = {"岗位", "职责", "要求", "我们", "相关", "工作", "负责", "熟悉", "优先", "经验"}


def build_match_report(
    *,
    head: ResumeHead,
    sections: list[ResumeSection],
    jd: JdProfile,
    resume_profile: ExtractedDocumentData | None,
) -> ResumeMatchReport:
    corpus = resume_corpus(head, sections)
    resume_skills = set(detect_skills(corpus))
    if resume_profile is not None:
        resume_skills |= normalize_skills(resume_profile.skills)
    required = normalize_skills(jd.required_skills)
    preferred = normalize_skills(jd.preferred_skills) - required
    matched_required = sorted(required & resume_skills)
    matched_preferred = sorted(preferred & resume_skills)
    required_coverage = len(matched_required) / len(required) if required else 1.0
    preferred_coverage = len(matched_preferred) / len(preferred) if preferred else 1.0

    terms = jd_terms(jd.raw_text)
    lowered = corpus.lower()
    matched_terms = [term for term in terms if term in lowered]
    semantic = len(matched_terms) / len(terms) if terms else 0.0
    interests = required | preferred
    domain = len(interests & resume_skills) / len(interests) if interests else 1.0
    gate = _evaluate_gate(jd=jd, head=head, resume_profile=resume_profile)
    preference = 1.0 if gate.checks.get("city", True) else 0.0
    freshness = _freshness(jd.published_at) if jd.job_id else 1.0

    weighted = (
        0.35 * required_coverage
        + 0.20 * preferred_coverage
        + 0.20 * semantic
        + 0.10 * domain
        + 0.10 * preference
        + 0.05 * freshness
    )
    missing_required = sorted(required - resume_skills)
    missing_preferred = sorted(preferred - resume_skills)
    skill_labels = sorted(
        {
            display_skill(skill)
            for skill in (*matched_required, *matched_preferred)
        }
    )
    label_keys = {label.lower() for label in skill_labels}
    extra_terms = {
        term
        for term in matched_terms
        if len(term) >= 3 and term not in resume_skills and term.lower() not in label_keys
    }
    keyword_hits = sorted(set(skill_labels) | extra_terms, key=str.lower)[:12]
    strengths: list[str] = []
    if matched_required:
        strengths.append(
            f"已覆盖必备技能：{'、'.join(display_skill(skill) for skill in matched_required)}"
        )
    if matched_preferred:
        strengths.append(
            f"具备加分技能：{'、'.join(display_skill(skill) for skill in matched_preferred)}"
        )
    gaps = [f"缺少必备技能：{display_skill(skill)}" for skill in missing_required]
    return ResumeMatchReport(
        source=jd.source,
        job_id=jd.job_id,
        jd_document_id=jd.document_id,
        jd_title=jd.title,
        company_name=jd.company_name,
        city=jd.city,
        eligible=gate.passed,
        total_score=round(weighted * 100, 2) if gate.passed else 0.0,
        breakdown=ScoreBreakdown(
            required_skill_coverage=round(required_coverage, 4),
            preferred_skill_coverage=round(preferred_coverage, 4),
            experience_semantic_score=round(semantic, 4),
            project_domain_score=round(domain, 4),
            preference_score=preference,
            freshness_score=freshness,
        ),
        hard_gate=gate,
        matched_required_skills=matched_required,
        missing_required_skills=missing_required,
        matched_preferred_skills=matched_preferred,
        missing_preferred_skills=missing_preferred,
        keyword_hits=keyword_hits,
        strengths=strengths,
        gaps=gaps,
        evidence=_evidence(sections=sections, terms=terms),
        scoring_version=SCORING_VERSION,
    )


def jd_terms(raw_text: str) -> list[str]:
    lowered = raw_text.lower()
    terms = {
        match.group(0).strip(".-")
        for match in LATIN_TERM.finditer(lowered)
        if match.group(0).strip(".-") not in STOPWORDS
    }
    for run in CJK_RUN.findall(raw_text):
        for index in range(len(run) - 1):
            bigram = run[index : index + 2]
            if bigram not in STOP_BIGRAMS:
                terms.add(bigram)
    return sorted(term for term in terms if len(term) >= 2)[:60]


def _evidence(*, sections: list[ResumeSection], terms: list[str], limit: int = 4) -> list[ResumeMatchEvidence]:
    scored: list[tuple[int, str, str, ResumeMatchEvidence]] = []
    for section in sections:
        for entry in section.entries:
            text = " ".join([entry_text(entry), *entry.bullets]).strip()
            if not text:
                continue
            lowered = text.lower()
            hits = sum(1 for term in terms if term in lowered)
            if hits == 0:
                continue
            scored.append(
                (
                    -hits,
                    section.id,
                    entry.id,
                    ResumeMatchEvidence(
                        section_id=section.id,
                        section_title=section.title,
                        entry_id=entry.id,
                        text=text[:300],
                    ),
                )
            )
    scored.sort(key=lambda item: item[:3])
    return [item[3] for item in scored[:limit]]


def _evaluate_gate(
    *,
    jd: JdProfile,
    head: ResumeHead,
    resume_profile: ExtractedDocumentData | None,
) -> HardGateResult:
    if jd.job is not None and resume_profile is not None:
        return evaluate_hard_gate(job=jd.job, profile=resume_profile)
    checks: dict[str, bool] = {}
    reasons: list[str] = []
    unknowns: list[str] = []
    if jd.job is not None:
        unknowns.append("简历缺少解析文档，已跳过每周到岗天数与实习周期检查")
        city = (head.city or "").strip()
        if jd.job.city:
            matched = bool(city) and (jd.job.city in city or city in jd.job.city)
            checks["city"] = matched
            if not matched:
                if city:
                    reasons.append(f"职位城市 {jd.job.city} 与简历城市 {city} 不一致")
                else:
                    unknowns.append("简历未填写城市")
    else:
        unknowns.append("JD 没有关联职位记录，未检查城市与到岗硬条件")
    return HardGateResult(
        passed=all(checks.values()), checks=checks, reasons=reasons, unknowns=unknowns
    )


def _freshness(published_at: datetime | None) -> float:
    if published_at is None:
        return 1.0
    created_at = published_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_days = max((datetime.now(timezone.utc) - created_at).days, 0)
    return 1.0 if age_days <= 30 else 0.7 if age_days <= 90 else 0.4
