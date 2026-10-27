"""Grounded rewrite suggestions for a resume workspace.

Every suggestion is derived from text the user already wrote plus the target JD.
Suggestions that would require inventing a new fact are marked `applicable=False`
so they can be shown as a to-do list but never written into the resume silently.
"""

from app.domains.matching.skills import detect_skills, display_skill, normalize_skills
from app.domains.resumes.jd import JdProfile
from app.domains.resumes.model import ResumeSectionKey
from app.domains.resumes.parser import entry_text, section_text
from app.domains.resumes.schemas import (
    MAX_BULLETS_PER_ENTRY,
    ResumeCitation,
    ResumeEntry,
    ResumeHead,
    ResumeMatchReport,
    ResumeSection,
    ResumeSuggestion,
)

GENERATOR_VERSION = "resume-optimize-v1"
MAX_SUGGESTIONS = 12
SKILL_ENTRY_TITLE = "技能关键词"
WEAK_VERBS = {
    "负责": "主导",
    "参与": "参与并交付",
    "协助": "协作完成",
    "帮助": "推动",
    "配合": "协同推进",
    "进行": "实施",
    "完成": "交付",
}
# Already-strong openings: rewriting them would only produce awkward double verbs
# when a user regenerates suggestions after applying the previous draft.
STRONG_PREFIXES = set(WEAK_VERBS.values()) | {
    "主导",
    "设计",
    "搭建",
    "实现",
    "构建",
    "推进",
    "交付",
    "协作",
    "协同",
    "推动",
    "实施",
}
KIND_ORDER = {
    "rewrite_bullet": 0,
    "add_skill": 1,
    "add_section": 2,
    "add_bullet": 3,
    "gap_plan": 4,
}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def generate_suggestions(
    *,
    sections: list[ResumeSection],
    jd: JdProfile,
    report: ResumeMatchReport,
    focus: str | None,
) -> list[ResumeSuggestion]:
    required = normalize_skills(jd.required_skills)
    preferred = normalize_skills(jd.preferred_skills) - required
    interests = required | preferred
    focus_skills = set(detect_skills(focus)) if focus else set()
    skill_section = next((s for s in sections if s.key == ResumeSectionKey.skill), None)
    project_section = next((s for s in sections if s.key == ResumeSectionKey.project), None)
    listed_skills = set(detect_skills(section_text(skill_section))) if skill_section else set()
    candidates: list[ResumeSuggestion] = []

    def priority_for(keywords: list[str]) -> str:
        return "high" if focus_skills & set(keywords) else "medium"

    # 1) Replace weak verbs with verifiable action verbs, keeping every fact intact.
    rewrite_budget = 4
    for section in sections:
        if section.key not in {ResumeSectionKey.project, ResumeSectionKey.experience}:
            continue
        for entry in section.entries:
            for bullet_index, bullet in enumerate(entry.bullets):
                if rewrite_budget <= 0:
                    break
                proposed = rewrite_weak_verb(bullet)
                if proposed is None:
                    continue
                keywords = [skill for skill in detect_skills(bullet) if skill in interests]
                candidates.append(
                    ResumeSuggestion(
                        id="",
                        kind="rewrite_bullet",
                        section_id=section.id,
                        entry_id=entry.id,
                        bullet_index=bullet_index,
                        title=f"强化「{section.title}」的动作表述",
                        original=bullet,
                        proposed=proposed,
                        rationale="把弱动词换为可验证的动作表述，其余事实、技术栈与数字保持不变。",
                        keywords=keywords,
                        citations=[
                            ResumeCitation(
                                source_type="resume_entry",
                                source_id=entry.id,
                                quote=bullet[:400],
                            )
                        ],
                        priority=priority_for(keywords),
                        confidence=0.72,
                    )
                )
                rewrite_budget -= 1
            if rewrite_budget <= 0:
                break

    # 2) A technology appears in the entry header but never in its bullets.
    add_bullet_budget = 3
    for section in sections:
        if section.key not in {ResumeSectionKey.project, ResumeSectionKey.experience}:
            continue
        for entry in section.entries:
            if add_bullet_budget <= 0:
                break
            entry_budget = 2
            header_skills = set(detect_skills(entry.subtitle or "")) & interests
            bullet_skills = set(detect_skills("\n".join(entry.bullets)))
            for skill in sorted(header_skills - bullet_skills):
                if add_bullet_budget <= 0 or entry_budget <= 0:
                    break
                candidates.append(
                    ResumeSuggestion(
                        id="",
                        kind="add_bullet",
                        section_id=section.id,
                        entry_id=entry.id,
                        title=f"补充 {display_skill(skill)} 的具体贡献",
                        original=entry.subtitle,
                        proposed=(
                            f"说明 {display_skill(skill)} 在这段经历中的具体职责、产出与量化结果"
                        ),
                        rationale=(
                            "技术栈里已经写了这项能力，但描述没有落到可验证的贡献；"
                            "补充真实细节后才能通过 JD 关键词筛选。"
                        ),
                        keywords=[skill],
                        citations=[
                            _entry_citation(entry),
                            _jd_citation(jd, skill),
                        ],
                        priority=priority_for([skill]),
                        confidence=0.55,
                        requires_new_fact=True,
                        applicable=False,
                    )
                )
                add_bullet_budget -= 1
                entry_budget -= 1

    # 3) Skills already evidenced in the resume body but missing from the skill list.
    add_skill_budget = 5
    evidenced = sorted(
        (set(report.matched_required_skills) | set(report.matched_preferred_skills))
        - listed_skills
    )
    for skill in evidenced:
        if add_skill_budget <= 0 or skill_section is None:
            break
        evidence = _skill_evidence(sections, skill)
        if evidence is None:
            continue
        evidence_section, evidence_entry, quote = evidence
        candidates.append(
            ResumeSuggestion(
                id="",
                kind="add_skill",
                section_id=skill_section.id,
                title=f"把 {display_skill(skill)} 写入专业技能",
                original=None,
                proposed=display_skill(skill),
                rationale=(
                    f"简历正文（{evidence_section.title}）已经出现这项能力，"
                    "写入技能清单可以让 JD 关键词筛选和人工浏览都直接命中。"
                ),
                keywords=[skill],
                citations=[
                    ResumeCitation(
                        source_type="resume_entry",
                        source_id=evidence_entry.id,
                        quote=quote[:400],
                    ),
                    _jd_citation(jd, skill),
                ],
                priority=priority_for([skill]),
                confidence=0.75,
            )
        )
        add_skill_budget -= 1

    # 4) Required skills without any evidence are a to-do, never an auto rewrite.
    for skill in report.missing_required_skills[:5]:
        candidates.append(
            ResumeSuggestion(
                id="",
                kind="gap_plan",
                section_id=(project_section.id if project_section is not None else sections[0].id),
                title=f"补强 {display_skill(skill)}",
                proposed=None,
                rationale=(
                    "这份 JD 的必备技能在简历中没有可验证证据。系统不会替你编造经历，"
                    "先完成一个可演示的小项目，再把真实结果补进项目经历。"
                ),
                keywords=[skill],
                citations=[_jd_citation(jd, skill)],
                priority="high" if skill in focus_skills else "medium",
                confidence=0.85,
                requires_new_fact=True,
                applicable=False,
            )
        )

    # 5) Fill an empty self-evaluation section with claims the resume already proves.
    summary = next((s for s in sections if s.key == ResumeSectionKey.summary), None)
    if summary is not None and not summary.entries:
        candidates.extend(
            _summary_suggestions(sections=sections, summary=summary, jd=jd, report=report)
        )

    # 6) Tell the user when a whole evidence section is still empty.
    for section in sections:
        if section.key not in {ResumeSectionKey.project, ResumeSectionKey.experience}:
            continue
        if section.entries:
            continue
        candidates.append(
            ResumeSuggestion(
                id="",
                kind="add_section",
                section_id=section.id,
                title=f"为「{section.title}」补充一段相关经历",
                proposed=(
                    f"补充一段与「{report.jd_title}」相关的{section.title}："
                    "写清背景、你的动作、使用的技术和可量化结果。"
                ),
                rationale="该章节目前为空，匹配报告需要可验证的经历证据。",
                keywords=[],
                citations=[_jd_citation(jd, next(iter(sorted(interests)), None))],
                priority="high",
                confidence=0.6,
                requires_new_fact=True,
                applicable=False,
            )
        )

    if not candidates:
        candidates.extend(_fallback_suggestions(sections=sections, jd=jd))

    return _finalize(candidates)


def rewrite_weak_verb(bullet: str) -> str | None:
    text = bullet.strip()
    if any(text.startswith(prefix) for prefix in STRONG_PREFIXES):
        return None
    for weak, strong in WEAK_VERBS.items():
        if text.startswith(weak):
            remainder = text[len(weak) :].lstrip(" ，,、")
            if not remainder or remainder.startswith(("并", "了", "过")):
                return None
            return f"{strong} {remainder}"[:600]
    return None


def apply_suggestions(
    *,
    head: ResumeHead,
    sections: list[ResumeSection],
    suggestions: list[ResumeSuggestion],
) -> tuple[ResumeHead, list[ResumeSection], list[str]]:
    """Apply only `applicable` suggestions to a deep-copied resume structure."""

    applied: list[str] = []
    section_map = {section.id: section for section in sections}
    for suggestion in suggestions:
        if not suggestion.applicable or not suggestion.proposed:
            continue
        section = section_map.get(suggestion.section_id)
        if section is None:
            continue
        if suggestion.kind == "rewrite_bullet":
            entry = _find_entry(section, suggestion.entry_id)
            if entry is None:
                continue
            proposed = suggestion.proposed[:600]
            if suggestion.bullet_index is not None and suggestion.bullet_index < len(entry.bullets):
                entry.bullets[suggestion.bullet_index] = proposed
            elif not entry.bullets:
                entry.title = proposed[:300]
            else:
                continue
            applied.append(suggestion.id)
        elif suggestion.kind == "add_bullet":
            entry = _find_entry(section, suggestion.entry_id)
            if entry is None or len(entry.bullets) >= MAX_BULLETS_PER_ENTRY:
                continue
            if suggestion.proposed in entry.bullets:
                continue
            entry.bullets.append(suggestion.proposed[:600])
            applied.append(suggestion.id)
        elif suggestion.kind == "add_skill":
            entry = next(
                (entry for entry in section.entries if entry.title == SKILL_ENTRY_TITLE), None
            )
            if entry is None:
                entry = ResumeEntry(id=_next_entry_id(section), title=SKILL_ENTRY_TITLE)
                section.entries.append(entry)
            if suggestion.proposed in entry.bullets:
                continue
            entry.bullets.append(suggestion.proposed[:600])
            applied.append(suggestion.id)
        elif suggestion.kind == "add_section":
            if len(section.entries) >= 30:
                continue
            section.entries.append(
                ResumeEntry(id=_next_entry_id(section), title=suggestion.proposed[:300])
            )
            applied.append(suggestion.id)
    return head, sections, applied


def find_mismatched_rewrites(
    *, sections: list[ResumeSection], suggestions: list[ResumeSuggestion]
) -> list[str]:
    """Detect suggestions whose original text no longer matches the resume."""

    section_map = {section.id: section for section in sections}
    mismatched: list[str] = []
    for suggestion in suggestions:
        if suggestion.kind != "rewrite_bullet" or not suggestion.original:
            continue
        section = section_map.get(suggestion.section_id)
        entry = _find_entry(section, suggestion.entry_id) if section is not None else None
        if entry is None:
            mismatched.append(suggestion.id)
            continue
        index = suggestion.bullet_index
        if index is not None and index < len(entry.bullets):
            if entry.bullets[index].strip() != suggestion.original.strip():
                mismatched.append(suggestion.id)
        elif entry.bullets:
            mismatched.append(suggestion.id)
    return mismatched


def _summary_suggestions(
    *,
    sections: list[ResumeSection],
    summary: ResumeSection,
    jd: JdProfile,
    report: ResumeMatchReport,
) -> list[ResumeSuggestion]:
    project_entries = [
        entry
        for section in sections
        if section.key == ResumeSectionKey.project
        for entry in section.entries
        if entry.title
    ]
    matched = report.matched_required_skills[:3] or report.matched_preferred_skills[:3]
    segments: list[str] = []
    citations: list[ResumeCitation] = []
    if matched:
        segments.append(f"具备 {'、'.join(display_skill(skill) for skill in matched)} 实践经验")
        citations.append(_jd_citation(jd, matched[0]))
    if project_entries:
        segments.append(f"完成过「{project_entries[0].title}」等可复用项目")
        citations.append(_entry_citation(project_entries[0]))
    if not segments or not citations:
        return []
    proposed = (
        "，".join(segments)
        + f"，与「{report.jd_title}」的要求吻合，可快速上手并独立交付。"
    )
    return [
        ResumeSuggestion(
            id="",
            kind="add_section",
            section_id=summary.id,
            title="生成自我评价建议稿",
            original=None,
            proposed=proposed[:600],
            rationale="自我评价目前为空；这段文字只复述简历里已有的技能和项目，不新增未经验证的事实。",
            keywords=[skill for skill in matched],
            citations=citations,
            priority="high" if matched else "medium",
            confidence=0.68,
        )
    ]


def _fallback_suggestions(
    *, sections: list[ResumeSection], jd: JdProfile
) -> list[ResumeSuggestion]:
    located = next(
        (
            (section, entry)
            for section in sections
            for entry in section.entries
            if entry.bullets
        ),
        None,
    )
    if located is None:
        return []
    section, entry = located
    return [
        ResumeSuggestion(
            id="",
            kind="add_bullet",
            section_id=section.id,
            entry_id=entry.id,
            title="补充可量化结果",
            original=entry.bullets[0],
            proposed="为该经历补充可量化结果（如用户量、提升比例、评测分数）",
            rationale=f"当前简历已覆盖「{jd.title}」的关键词，下一步最缺的是可验证的量化和结果。",
            keywords=[],
            citations=[_entry_citation(entry)],
            priority="medium",
            confidence=0.5,
            requires_new_fact=True,
            applicable=False,
        )
    ]


def _finalize(candidates: list[ResumeSuggestion]) -> list[ResumeSuggestion]:
    ordered = sorted(
        candidates,
        key=lambda item: (
            PRIORITY_ORDER.get(item.priority, 1),
            not item.applicable,
            KIND_ORDER.get(item.kind, 9),
        ),
    )[:MAX_SUGGESTIONS]
    result: list[ResumeSuggestion] = []
    for index, suggestion in enumerate(ordered, start=1):
        result.append(suggestion.model_copy(update={"id": f"sug-{index}"}))
    return result


def _find_entry(section: ResumeSection, entry_id: str | None) -> ResumeEntry | None:
    if entry_id is None:
        return None
    return next((entry for entry in section.entries if entry.id == entry_id), None)


def _next_entry_id(section: ResumeSection) -> str:
    existing = {entry.id for entry in section.entries}
    index = len(section.entries)
    while f"{section.id}-entry-{index}" in existing:
        index += 1
    return f"{section.id}-entry-{index}"


def _entry_citation(entry: ResumeEntry) -> ResumeCitation:
    quote = next(
        (bullet for bullet in entry.bullets if bullet),
        entry.title or entry.subtitle or entry_text(entry) or "简历条目",
    )
    return ResumeCitation(
        source_type="resume_entry",
        source_id=entry.id,
        quote=quote[:400],
    )


def _jd_citation(jd: JdProfile, skill: str | None) -> ResumeCitation:
    if jd.source == "job" and jd.job_id:
        source_type = "job"
        source_id = jd.job_id
    elif jd.source == "announcement" and jd.announcement_id:
        source_type = "announcement"
        source_id = jd.announcement_id
    elif jd.source == "document" and jd.document_id:
        source_type = "jd_document"
        source_id = jd.document_id
    else:
        source_type = "jd_text"
        source_id = "inline"
    quote = display_skill(skill) if skill else (jd.raw_text.strip()[:120] or jd.title)
    return ResumeCitation(source_type=source_type, source_id=source_id, quote=quote[:400])


def _skill_evidence(
    sections: list[ResumeSection], skill: str
) -> tuple[ResumeSection, ResumeEntry, str] | None:
    for section in sections:
        for entry in section.entries:
            for bullet in entry.bullets:
                if skill in detect_skills(bullet):
                    return section, entry, bullet
            for text in (entry.title, entry.subtitle or ""):
                if text and skill in detect_skills(text):
                    return section, entry, text
    return None
