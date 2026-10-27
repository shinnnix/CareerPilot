"""Deterministic resume structure analysis.

Uploads are still stored as knowledge documents (normalized text + chunks) by the
documents domain. This module turns the same text into the editable resume
structure the workspace renders, so both views stay derived from one source.
"""

import re
from dataclasses import dataclass

from app.domains.documents.parser import normalize_text, split_sections
from app.domains.resumes.model import ResumeSectionKey
from app.domains.resumes.schemas import (
    MAX_BULLETS_PER_ENTRY,
    MAX_ENTRIES_PER_SECTION,
    ResumeEntry,
    ResumeHead,
    ResumeLink,
    ResumeSection,
)

RESUME_STRUCTURE_VERSION = "resume-structure-v1"

CORE_SECTIONS: tuple[tuple[ResumeSectionKey, str], ...] = (
    (ResumeSectionKey.education, "教育经历"),
    (ResumeSectionKey.experience, "工作/实习经历"),
    (ResumeSectionKey.project, "项目经历"),
    (ResumeSectionKey.skill, "专业技能"),
    (ResumeSectionKey.summary, "自我评价"),
)

SECTION_ALIASES: dict[str, ResumeSectionKey] = {
    "教育经历": ResumeSectionKey.education,
    "教育背景": ResumeSectionKey.education,
    "学历背景": ResumeSectionKey.education,
    "教育与培训": ResumeSectionKey.education,
    "工作经历": ResumeSectionKey.experience,
    "实习经历": ResumeSectionKey.experience,
    "工作/实习经历": ResumeSectionKey.experience,
    "工作/实习": ResumeSectionKey.experience,
    "实习/工作经历": ResumeSectionKey.experience,
    "实践经历": ResumeSectionKey.experience,
    "职业经历": ResumeSectionKey.experience,
    "项目经历": ResumeSectionKey.project,
    "项目经验": ResumeSectionKey.project,
    "项目实践": ResumeSectionKey.project,
    "科研经历": ResumeSectionKey.project,
    "专业技能": ResumeSectionKey.skill,
    "技能清单": ResumeSectionKey.skill,
    "技能特长": ResumeSectionKey.skill,
    "技术栈": ResumeSectionKey.skill,
    "技能": ResumeSectionKey.skill,
    "自我评价": ResumeSectionKey.summary,
    "自我介绍": ResumeSectionKey.summary,
    "个人简介": ResumeSectionKey.summary,
    "个人总结": ResumeSectionKey.summary,
    "个人优势": ResumeSectionKey.summary,
}

BASIC_ALIASES = {"基本信息", "个人信息", "联系方式", "求职意向", "个人资料"}

PARAGRAPH_SECTIONS = {ResumeSectionKey.summary, ResumeSectionKey.other}

HEAD_STOPWORDS = {
    "个人简历",
    "简历",
    "求职简历",
    "中文简历",
    "英文简历",
    "resume",
    "cv",
    "curriculum vitae",
}

PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
URL_PATTERN = re.compile(r"https?://[^\s，。；、)）]+")
CJK_NAME_PATTERN = re.compile(r"^[\u4e00-\u9fa5·]{2,12}$")
LATIN_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,30}$")
BULLET_PATTERN = re.compile(
    r"^\s*(?:[-*•·●▪◦‣]|\d{1,2}\s*[.)、]|[（(]\s*\d{1,2}\s*[)）])\s*"
)
PERIOD_PATTERN = re.compile(
    r"(?:(?:19|20)\d{2}\s*[.\-/年]?\s*\d{0,2}\s*月?\s*[-–—~至－]\s*"
    r"(?:(?:19|20)\d{2}\s*[.\-/年]?\s*\d{0,2}\s*月?|至今|现在|今))"
)
WHITESPACE_RUN = re.compile(r"\s{2,}|\t")


@dataclass(frozen=True)
class ParsedResume:
    head: ResumeHead
    sections: list[ResumeSection]
    detected_section_titles: list[str]
    warnings: list[str]
    confidence: float


def parse_resume_content(*, raw_text: str, display_name: str) -> ParsedResume:
    normalized = normalize_text(raw_text)
    head_lines: list[str] = []
    buckets: dict[ResumeSectionKey, list[str]] = {}
    section_titles: dict[ResumeSectionKey, str] = {}
    other_sections: list[tuple[str, list[str]]] = []
    detected_titles: list[str] = []
    warnings: list[str] = []

    raw_sections = split_sections(normalized)
    saw_head_block = False
    for index, section in enumerate(raw_sections):
        title = section.title.strip()
        key = _section_key(title)
        if key is None and _normalize_title(title) in BASIC_ALIASES:
            head_lines.extend(section.content.splitlines())
            saw_head_block = True
            continue
        if key is None and title == "正文" and index == 0 and not saw_head_block:
            head_lines.extend(section.content.splitlines())
            saw_head_block = True
            continue
        if key is None:
            other_sections.append((title, section.content.splitlines()))
            continue
        detected_titles.append(title)
        section_titles.setdefault(key, title)
        buckets.setdefault(key, []).extend(section.content.splitlines())

    head = parse_head(head_lines=head_lines, full_text=normalized)

    sections: list[ResumeSection] = []
    for key, default_title in CORE_SECTIONS:
        lines = buckets.pop(key, [])
        section_title = section_titles.get(key, default_title)
        if not lines:
            warnings.append(f"未识别到「{section_title}」章节，已保留空白章节供人工补充")
        sections.append(
            _build_section(
                key=key,
                title=section_title,
                lines=lines,
                position=len(sections),
            )
        )
    for title, lines in other_sections:
        sections.append(
            _build_section(
                key=ResumeSectionKey.other,
                title=title,
                lines=lines,
                position=len(sections),
            )
        )

    confidence = _confidence(head=head, detected=detected_titles, sections=sections)
    if not head.name:
        warnings.append("未识别到姓名，请在「基本信息」中补充")
    return ParsedResume(
        head=head,
        sections=sections,
        detected_section_titles=detected_titles,
        warnings=warnings,
        confidence=confidence,
    )


def parse_head(*, head_lines: list[str], full_text: str) -> ResumeHead:
    lines = [line.strip() for line in head_lines if line.strip()]
    name = next((line for line in lines[:8] if _is_name_line(line)), None)
    if name is None:
        name = next(
            (
                line.strip()
                for line in full_text.splitlines()[:6]
                if _is_name_line(line.strip())
            ),
            None,
        )
    email = EMAIL_PATTERN.search(full_text)
    phone = PHONE_PATTERN.search(full_text)
    links: list[ResumeLink] = []
    for url in URL_PATTERN.findall(full_text)[:5]:
        if any(link.url == url for link in links):
            continue
        links.append(ResumeLink(label=_link_label(url), url=url))
    return ResumeHead(
        name=name,
        target_title=_labeled_value(
            full_text, ("目标岗位", "求职意向", "应聘岗位", "意向岗位", "求职目标")
        ),
        phone=phone.group(0) if phone else None,
        email=email.group(0) if email else None,
        city=_labeled_value(
            full_text, ("期望城市", "意向城市", "所在城市", "现居城市", "城市")
        ),
        links=links,
    )


def entry_text(entry: ResumeEntry) -> str:
    parts = [entry.title, entry.subtitle or "", entry.period or ""]
    return " ".join(part for part in parts if part).strip()


def section_text(section: ResumeSection) -> str:
    lines: list[str] = []
    for entry in section.entries:
        header = entry_text(entry)
        if header:
            lines.append(header)
        lines.extend(entry.bullets)
    return "\n".join(lines)


def resume_corpus(head: ResumeHead, sections: list[ResumeSection]) -> str:
    """Flatten every editable field so detection sees user edits, not the upload."""

    parts = [
        head.name or "",
        head.target_title or "",
        head.city or "",
        head.email or "",
        head.phone or "",
        " ".join(link.url for link in head.links),
    ]
    parts.extend(section.title for section in sections)
    parts.extend(section_text(section) for section in sections)
    return "\n".join(part for part in parts if part)


def _section_key(title: str) -> ResumeSectionKey | None:
    return SECTION_ALIASES.get(_normalize_title(title))


def _normalize_title(title: str) -> str:
    return re.sub(r"[\s：:·]+", "", title.strip())


def _build_section(
    *,
    key: ResumeSectionKey,
    title: str,
    lines: list[str],
    position: int,
) -> ResumeSection:
    section_id = f"section-{position}"
    if key in PARAGRAPH_SECTIONS:
        entries = _build_paragraph_entries(lines=lines, section_id=section_id)
    else:
        entries = _build_timeline_entries(lines=lines, section_id=section_id)
    return ResumeSection(
        id=section_id,
        key=key,
        title=title.strip()[:50] or key.value,
        entries=entries[:MAX_ENTRIES_PER_SECTION],
    )


def _build_timeline_entries(*, lines: list[str], section_id: str) -> list[ResumeEntry]:
    entries: list[ResumeEntry] = []
    current: ResumeEntry | None = None
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        bullet = _strip_bullet(raw_line)
        if bullet is not None:
            if current is None:
                current = _new_entry(section_id=section_id, index=len(entries))
                entries.append(current)
            if len(current.bullets) < MAX_BULLETS_PER_ENTRY:
                current.bullets.append(bullet)
            continue
        title, subtitle, period = _split_header(line)
        if current is None or current.bullets:
            current = _new_entry(
                section_id=section_id,
                index=len(entries),
                title=title,
                subtitle=subtitle,
                period=period,
            )
            entries.append(current)
            continue
        if current.period is None and period:
            current.period = period
        if not current.title:
            current.title = title
        elif subtitle:
            current.subtitle = (
                f"{current.subtitle} {subtitle}".strip() if current.subtitle else subtitle
            )
        elif title:
            current.subtitle = (
                f"{current.subtitle} {title}".strip() if current.subtitle else title
            )
    return entries


def _build_paragraph_entries(*, lines: list[str], section_id: str) -> list[ResumeEntry]:
    entries: list[ResumeEntry] = []
    paragraph: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            _flush_paragraph(entries, paragraph, section_id)
            paragraph = []
            continue
        bullet = _strip_bullet(raw_line)
        if bullet is not None:
            _flush_paragraph(entries, paragraph, section_id)
            paragraph = []
            entries.append(
                _new_entry(section_id=section_id, index=len(entries), bullets=[bullet])
            )
            continue
        paragraph.append(line)
    _flush_paragraph(entries, paragraph, section_id)
    return entries


def _flush_paragraph(
    entries: list[ResumeEntry], paragraph: list[str], section_id: str
) -> None:
    text = " ".join(paragraph).strip()
    if not text:
        return
    entries.append(
        _new_entry(section_id=section_id, index=len(entries), title=text[:300])
    )


def _new_entry(
    *,
    section_id: str,
    index: int,
    title: str = "",
    subtitle: str | None = None,
    period: str | None = None,
    bullets: list[str] | None = None,
) -> ResumeEntry:
    return ResumeEntry(
        id=f"{section_id}-entry-{index}",
        title=title[:300],
        subtitle=subtitle[:300] if subtitle else None,
        period=period[:100] if period else None,
        bullets=(bullets or [])[:MAX_BULLETS_PER_ENTRY],
    )


def _strip_bullet(line: str) -> str | None:
    match = BULLET_PATTERN.match(line)
    if match is None:
        return None
    text = line[match.end() :].strip()
    if not text:
        return None
    return text[:600]


def _split_header(text: str) -> tuple[str, str | None, str | None]:
    cleaned = text.strip().strip("｜|·,，;；")
    period: str | None = None
    match = PERIOD_PATTERN.search(cleaned)
    if match:
        period = _normalize_period(match.group(0))
        cleaned = f"{cleaned[: match.start()]} {cleaned[match.end():]}"
        cleaned = re.sub(r"[\s,，;；|｜]+$", "", cleaned).strip()
    title = cleaned
    subtitle: str | None = None
    for separator in ("|", "｜", "•"):
        if separator in cleaned:
            left, _, right = cleaned.partition(separator)
            title = left.strip()
            subtitle = right.strip() or None
            break
    else:
        parts = [part.strip() for part in WHITESPACE_RUN.split(cleaned) if part.strip()]
        if len(parts) >= 2:
            title = parts[0]
            subtitle = " ".join(parts[1:])
    if not title and subtitle:
        title, subtitle = subtitle, None
    return title[:300], (subtitle[:300] if subtitle else None), period


def _normalize_period(raw: str) -> str:
    collapsed = re.sub(r"\s+", "", raw.strip())
    return collapsed.replace("—", "-").replace("–", "-").replace("~", "-").replace("－", "-")[:100]


def _labeled_value(text: str, labels: tuple[str, ...]) -> str | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:^|[（(\s])[（(\[]?(?:{label_pattern})[)）\]]?\s*[：:]\s*([^\n，,；;|｜]{{1,60}})",
        text,
        flags=re.MULTILINE,
    )
    return match.group(1).strip() if match else None


def _is_name_line(line: str) -> bool:
    if not line or len(line) > 40:
        return False
    lowered = line.lower()
    if lowered in HEAD_STOPWORDS or line in HEAD_STOPWORDS:
        return False
    if any(character.isdigit() for character in line):
        return False
    if line.startswith(("#", "-", "*", "•", "·")):
        return False
    if "@" in line or "http" in lowered or "_" in line:
        return False
    if "：" in line or ":" in line:
        return False
    if _section_key(line) is not None or _normalize_title(line) in BASIC_ALIASES:
        return False
    return bool(CJK_NAME_PATTERN.fullmatch(line) or LATIN_NAME_PATTERN.fullmatch(line))


def _link_label(url: str) -> str:
    stripped = re.sub(r"^https?://", "", url).strip("/")
    host = stripped.split("/", 1)[0].lower()
    if "github" in host:
        return "GitHub"
    if "linkedin" in host:
        return "LinkedIn"
    if "gitee" in host:
        return "Gitee"
    if "blog" in host or "notion" in host:
        return "主页"
    return host[:40] or "链接"


def _confidence(*, head: ResumeHead, detected: list[str], sections: list[ResumeSection]) -> float:
    score = 0.35
    score += min(len(detected), 5) * 0.08
    score += 0.15 if head.name else 0.0
    score += 0.10 if head.email or head.phone else 0.0
    if any(section.entries for section in sections if section.key.value == "project"):
        score += 0.07
    if any(section.entries for section in sections if section.key.value == "experience"):
        score += 0.05
    return round(min(score, 0.95), 4)
