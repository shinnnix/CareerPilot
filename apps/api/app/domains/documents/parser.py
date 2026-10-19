import hashlib
import re
from dataclasses import dataclass

from app.domains.documents.model import DocumentType
from app.domains.documents.schemas import ExtractedDocumentData

PARSER_VERSION = "rule-parser-v1"
INDEX_VERSION = "title-aware-v1"
MAX_CHUNK_CHARS = 600
CHUNK_OVERLAP_CHARS = 80

KNOWN_HEADINGS = {
    "个人简介",
    "个人信息",
    "教育经历",
    "项目经历",
    "实习经历",
    "工作经历",
    "专业技能",
    "技能清单",
    "获奖经历",
    "自我评价",
    "职位描述",
    "岗位描述",
    "岗位职责",
    "工作职责",
    "任职要求",
    "岗位要求",
    "职位要求",
    "基本要求",
    "加分项",
    "优先条件",
    "公司介绍",
    "福利待遇",
}

SKILL_ALIASES = {
    "python": ["python"],
    "fastapi": ["fastapi"],
    "vue": ["vue.js", "vue3", "vue 3", "vue"],
    "typescript": ["typescript"],
    "javascript": ["javascript"],
    "langchain": ["langchain"],
    "langgraph": ["langgraph"],
    "rag": ["检索增强生成", "rag"],
    "postgresql": ["postgresql", "postgres"],
    "pgvector": ["pgvector"],
    "docker": ["docker"],
    "redis": ["redis"],
    "sqlalchemy": ["sqlalchemy"],
    "pytorch": ["pytorch"],
    "transformers": ["transformers"],
    "llm": ["大语言模型", "大模型", "llm"],
}

SECTION_TYPES = {
    "岗位职责": "responsibility",
    "工作职责": "responsibility",
    "任职要求": "requirement",
    "岗位要求": "requirement",
    "职位要求": "requirement",
    "基本要求": "requirement",
    "加分项": "preferred_requirement",
    "优先条件": "preferred_requirement",
    "项目经历": "experience",
    "实习经历": "experience",
    "工作经历": "experience",
    "教育经历": "education",
    "专业技能": "skill",
    "技能清单": "skill",
}


@dataclass(frozen=True)
class ParsedSection:
    title: str
    content: str


@dataclass(frozen=True)
class ParsedChunk:
    position: int
    section_path: list[str]
    chunk_type: str
    content: str
    contextualized_content: str
    char_count: int
    estimated_token_count: int
    content_hash: str


@dataclass(frozen=True)
class ParseResult:
    normalized_text: str
    content_hash: str
    extracted_data: ExtractedDocumentData
    confidence: float
    sections: list[ParsedSection]
    chunks: list[ParsedChunk]


def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    normalized = "\n".join(line.rstrip() for line in normalized.splitlines())
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def hash_text(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def parse_document(*, raw_text: str, document_type: DocumentType, display_name: str) -> ParseResult:
    normalized = normalize_text(raw_text)
    sections = split_sections(normalized)
    extracted = extract_structured_data(
        text=normalized,
        document_type=document_type,
        sections=sections,
        display_name=display_name,
    )
    confidence = calculate_confidence(document_type, extracted, sections)
    chunks = build_chunks(display_name=display_name, sections=sections)
    return ParseResult(
        normalized_text=normalized,
        content_hash=hash_text(normalized),
        extracted_data=extracted,
        confidence=confidence,
        sections=sections,
        chunks=chunks,
    )


def split_sections(text: str) -> list[ParsedSection]:
    sections: list[ParsedSection] = []
    current_title = "正文"
    current_lines: list[str] = []

    def flush() -> None:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append(ParsedSection(title=current_title, content=content))

    for line in text.splitlines():
        heading = detect_heading(line)
        if heading:
            flush()
            current_title = heading
            current_lines = []
        else:
            current_lines.append(line)
    flush()
    return sections or [ParsedSection(title="正文", content=text)]


def detect_heading(line: str) -> str | None:
    stripped = line.strip()
    if not stripped:
        return None
    markdown = re.match(r"^#{1,6}\s+(.+?)\s*$", stripped)
    if markdown:
        return markdown.group(1).strip().rstrip("：:")
    candidate = stripped.rstrip("：:").strip()
    if candidate in KNOWN_HEADINGS:
        return candidate
    if len(candidate) <= 16 and stripped.endswith(("：", ":")) and not re.search(r"\d", candidate):
        return candidate
    return None


def extract_structured_data(
    *,
    text: str,
    document_type: DocumentType,
    sections: list[ParsedSection],
    display_name: str,
) -> ExtractedDocumentData:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), None)
    title = _match_field(text, ["职位", "岗位名称", "应聘岗位"])
    company_name = _match_field(text, ["公司", "公司名称"])
    city = _match_field(text, ["城市", "工作地点", "地点"])
    email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    phone_match = re.search(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", text)
    skills = _extract_skills(text)
    desired_city = _match_field(text, ["期望城市", "意向城市"])
    days_match = re.search(r"(?:每周可实习|每周到岗)\s*(\d)\s*天", text)
    months_match = re.search(r"(?:可实习|实习周期)\s*(\d{1,2})\s*个?月", text)

    if document_type == DocumentType.job_description and not title:
        title = first_line if first_line and len(first_line) <= 100 else display_name
    if document_type == DocumentType.resume and not title:
        title = display_name

    return ExtractedDocumentData(
        title=title,
        company_name=company_name,
        city=city,
        email=email_match.group(0) if email_match else None,
        phone=phone_match.group(0) if phone_match else None,
        skills=skills,
        section_titles=[section.title for section in sections],
        desired_cities=[desired_city] if desired_city else [],
        available_days_per_week=int(days_match.group(1)) if days_match else None,
        available_months=int(months_match.group(1)) if months_match else None,
    )


def _match_field(text: str, labels: list[str]) -> str | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"^(?:{label_pattern})\s*[：:]\s*([^\n]{{1,200}})$",
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _extract_skills(text: str) -> list[str]:
    lowered = text.lower()
    detected = [
        canonical
        for canonical, aliases in SKILL_ALIASES.items()
        if any(_contains_alias(lowered, alias.lower()) for alias in aliases)
    ]
    return sorted(detected)


def _contains_alias(text: str, alias: str) -> bool:
    if re.fullmatch(r"[a-z0-9 .+-]+", alias):
        return bool(
            re.search(
                rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",
                text,
                flags=re.IGNORECASE,
            )
        )
    return alias in text


def calculate_confidence(
    document_type: DocumentType,
    extracted: ExtractedDocumentData,
    sections: list[ParsedSection],
) -> float:
    score = 0.30
    if any(section.title != "正文" for section in sections):
        score += 0.20
    if extracted.skills:
        score += 0.15
    if document_type == DocumentType.job_description:
        score += 0.15 if extracted.title else 0
        score += 0.10 if extracted.company_name or extracted.city else 0
    elif document_type == DocumentType.resume:
        score += 0.10 if extracted.email or extracted.phone else 0
        score += 0.10 if len(sections) >= 2 else 0
    else:
        score += 0.10 if len(sections) >= 2 else 0
    return round(min(score, 0.95), 4)


def build_chunks(*, display_name: str, sections: list[ParsedSection]) -> list[ParsedChunk]:
    chunks: list[ParsedChunk] = []
    for section in sections:
        for piece in split_section_content(section.content):
            contextualized = f"文档：{display_name}\n章节：{section.title}\n{piece}"
            chunks.append(
                ParsedChunk(
                    position=len(chunks),
                    section_path=[display_name, section.title],
                    chunk_type=SECTION_TYPES.get(section.title, "paragraph"),
                    content=piece,
                    contextualized_content=contextualized,
                    char_count=len(piece),
                    estimated_token_count=max(1, (len(contextualized) + 1) // 2),
                    content_hash=hashlib.sha256(piece.encode("utf-8")).hexdigest(),
                )
            )
    return chunks


def split_section_content(content: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", content) if block.strip()]
    pieces: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        is_list = len(lines) > 1 and sum(_is_list_item(line) for line in lines) >= len(lines) / 2
        candidates = lines if is_list else [block]
        for candidate in candidates:
            cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.)、])\s*", "", candidate).strip()
            pieces.extend(_split_long_text(cleaned))
    return [piece for piece in pieces if piece]


def _is_list_item(line: str) -> bool:
    return bool(re.match(r"^\s*(?:[-*•]|\d+[.)、])\s*", line))


def _split_long_text(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    pieces: list[str] = []
    start = 0
    while start < len(text):
        target_end = min(start + MAX_CHUNK_CHARS, len(text))
        end = target_end
        if target_end < len(text):
            boundary = max(
                text.rfind(mark, start + MAX_CHUNK_CHARS // 2, target_end)
                for mark in ("。", "！", "？", ";", "；", "\n")
            )
            if boundary > start:
                end = boundary + 1
        pieces.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP_CHARS, start + 1)
    return pieces
