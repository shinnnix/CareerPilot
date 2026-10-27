"""Rule-first announcement extraction (plan §2.7.1).

The extractor is pure local, dependency free and always runs. When AI
credentials are configured an LLM pass may enrich the result later; conflicts
keep the rule value and are flagged ``needs_review``. Nothing here may raise on
messy input — a partial draft is a valid outcome.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from app.domains.jobs.constants import RECRUITMENT_TYPES

COMPANY_SUFFIXES = ("公司", "集团", "银行", "研究院", "研究所", "事务所", "科技", "事业部", "工厂")

CITY_DICTIONARY = ["北京", "上海", "广州", "深圳", "杭州", "南京", "苏州", "成都", "武汉", "西安", "重庆", "天津", "长沙", "合肥", "郑州", "济南", "青岛", "厦门", "福州", "南昌", "宁波", "无锡", "东莞", "佛山", "珠海", "中山", "惠州", "昆明", "贵阳", "南宁", "海口", "太原", "石家庄", "沈阳", "大连", "长春", "哈尔滨", "兰州", "银川", "西宁", "乌鲁木齐", "呼和浩特", "海外", "香港", "澳门", "台北"]

TITLE_PREFIX_NOISE = re.compile(r"^(重磅|独家|速看|收藏|转发|扩散|通知)[:：!！\s]*")
TITLE_EDGE_NOISE = re.compile(r"^[\s\-—|｜:：,，.。;；]+|[\s\-—|｜:：,，.。;；!！~～]+$")

POSITION_HEADINGS = (
    "招聘岗位",
    "招聘职位",
    "岗位需求",
    "岗位信息",
    "岗位列表",
    "职位列表",
    "招聘计划",
    "招聘专业",
    "开放岗位",
    "热招岗位",
)

LOCATION_KEYS = ("工作地点", "工作城市", "办公地点", "工作地址", "地点", "城市", "工作地")

DEADLINE_KEYS = ("截止时间", "报名截止", "投递截止", "简历投递截止", "截止日期", "截止")

DATE_PATTERN = re.compile(
    r"(20\d{2})\s*[年.\-/]\s*(\d{1,2})\s*[月.\-/]\s*(\d{1,2})\s*日?"
)
MONTH_DAY_PATTERN = re.compile(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*日?")
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
URL_PATTERN = re.compile(r"https?://[^\s，,。；;、)）\]】\"'<>]+")
COHORT_PATTERN = re.compile(r"(20\d{2})\s*届")


@dataclass
class ParsedAnnouncement:
    title: str | None = None
    company_name: str | None = None
    recruitment_type: str | None = None
    target_cohort: str | None = None
    locations: list[str] = field(default_factory=list)
    positions: list[str] = field(default_factory=list)
    deadline_text: str | None = None
    deadline_at: datetime | None = None
    published_at: datetime | None = None
    apply_method: dict[str, object] = field(default_factory=dict)
    confidence: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "company_name": self.company_name,
            "recruitment_type": self.recruitment_type,
            "target_cohort": self.target_cohort,
            "locations": self.locations,
            "positions": self.positions,
            "deadline_text": self.deadline_text,
            "deadline_at": self.deadline_at.isoformat() if self.deadline_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "apply_method": self.apply_method,
            "confidence": self.confidence,
        }


def parse_announcement(
    raw_text: str,
    *,
    source_name: str | None = None,
    fallback_title: str | None = None,
    today: date | None = None,
) -> ParsedAnnouncement:
    text = _normalize(raw_text)
    reference = today or datetime.now(timezone.utc).date()
    lines = [line.strip() for line in text.split("\n")]
    non_empty = [line for line in lines if line]

    parsed = ParsedAnnouncement()
    parsed.title = _extract_title(non_empty, fallback_title)
    parsed.company_name = _extract_company(non_empty, source_name)
    parsed.recruitment_type = _extract_recruitment_type(text)
    parsed.target_cohort = _extract_cohort(text)
    parsed.locations = _extract_locations(text)
    parsed.positions = _extract_positions(non_empty)
    parsed.deadline_text, parsed.deadline_at = _extract_deadline(text, reference)
    parsed.published_at = _extract_published_at(non_empty, reference)
    parsed.apply_method = _extract_apply_method(text)
    parsed.confidence = _confidence(parsed)
    return parsed


def _normalize(raw_text: str) -> str:
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n").replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_title(value: str) -> str:
    cleaned = value.replace("【", "").replace("】", "").strip()
    cleaned = TITLE_PREFIX_NOISE.sub("", cleaned)
    cleaned = TITLE_EDGE_NOISE.sub("", cleaned)
    return cleaned[:300]


def _extract_title(lines: list[str], fallback: str | None) -> str | None:
    """Pick the most title-like line: recruitment wording, short, bracketed."""
    best: str | None = None
    best_score = -1
    for line in lines[:6]:
        if len(line) < 4 or len(line) > 120:
            continue
        if line.startswith(("发布", "来源", "点击", "阅读")):
            continue
        cleaned = _clean_title(line)
        if len(cleaned) < 4:
            continue
        score = 0
        if "招聘" in cleaned or "校招" in cleaned:
            score += 3
        if "公告" in cleaned or "简章" in cleaned or "启事" in cleaned:
            score += 2
        if len(cleaned) <= 40:
            score += 2
        elif len(cleaned) <= 60:
            score += 1
        if line.startswith("【"):
            score += 1
        if score > best_score:
            best, best_score = cleaned, score
    if best:
        return best
    if fallback:
        return _clean_title(fallback) or fallback[:300]
    return _clean_title(lines[0])[:300] if lines else None


def _extract_company(lines: list[str], source_name: str | None) -> str | None:
    head = "\n".join(lines[:8])
    bracket = re.search(r"【([^】]{2,30})】", head)
    if bracket:
        candidate = _clean_company(bracket.group(1))
        if candidate:
            return candidate

    labelled = re.search(
        r"(?:公司名称|企业名称|用人单位|公司)\s*[:：]\s*([^\n，,。;；]{2,40})", head
    )
    if labelled:
        candidate = _clean_company(labelled.group(1))
        if candidate:
            return candidate

    for line in lines[:6]:
        for suffix in COMPANY_SUFFIXES:
            match = re.search(rf"([\u4e00-\u9fa5A-Za-z0-9（）()]{{2,30}}{suffix})", line)
            if match:
                candidate = _clean_company(match.group(1))
                if candidate:
                    return candidate

    if source_name:
        candidate = _clean_company(source_name)
        if candidate:
            return candidate
    return None


def _clean_company(value: str) -> str | None:
    candidate = value.strip(" 【】[]（）()")
    candidate = re.sub(r"^(关于|来自|致|恭喜)", "", candidate).strip()
    if 2 <= len(candidate) <= 40:
        return candidate
    return None


def _extract_recruitment_type(text: str) -> str | None:
    for keyword, value in (
        ("秋招", "秋招"),
        ("秋季校园招聘", "秋招"),
        ("春招", "春招"),
        ("春季校园招聘", "春招"),
        ("补录", "补录"),
        ("实习", "实习"),
        ("社招", "社招"),
        ("社会招聘", "社招"),
    ):
        if keyword in text and value in RECRUITMENT_TYPES:
            return value
    if "校园招聘" in text or "校招" in text:
        return "秋招"
    return None


def _extract_cohort(text: str) -> str | None:
    match = COHORT_PATTERN.search(text)
    if match:
        return f"{match.group(1)}届"
    if "不限" in text and "届" in text:
        return "不限"
    return None


def _extract_locations(text: str) -> list[str]:
    found: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip(" -·*•\t")
        if not any(stripped.startswith(key) for key in LOCATION_KEYS):
            continue
        body = re.split(r"[:：]", stripped, maxsplit=1)
        if len(body) < 2:
            continue
        for chunk in re.split(r"[、，,/;；|\s]+", body[1]):
            city = _match_city(chunk)
            if city and city not in found:
                found.append(city)
        if found:
            return found[:8]

    for city in CITY_DICTIONARY:
        if city in text and city not in found:
            found.append(city)
    return found[:8]


def _match_city(chunk: str) -> str | None:
    candidate = chunk.strip()
    if not candidate or len(candidate) > 8:
        return None
    for city in CITY_DICTIONARY:
        if city in candidate:
            return city
    if candidate.endswith(("市", "省")) and 2 <= len(candidate) <= 6:
        return candidate
    return None


def _extract_positions(lines: list[str]) -> list[str]:
    positions: list[str] = []

    for index, line in enumerate(lines):
        if not any(heading in line for heading in POSITION_HEADINGS):
            continue
        inline = re.split(r"[:：]", line, maxsplit=1)
        if len(inline) == 2:
            positions.extend(_split_positions(inline[1]))
        for follower in lines[index + 1 : index + 14]:
            if not follower:
                break
            if any(key in follower for key in ("工作地点", "截止", "投递方式", "薪资")):
                break
            positions.extend(_split_positions(follower))
        if positions:
            break

    if not positions:
        for line in lines:
            if not line.startswith(("岗位", "职位")):
                continue
            inline = re.split(r"[:：]", line, maxsplit=1)
            if len(inline) == 2:
                positions.extend(_split_positions(inline[1]))
            if positions:
                break

    seen: list[str] = []
    for item in positions:
        if item not in seen:
            seen.append(item)
    return seen[:30]


def _split_positions(value: str) -> list[str]:
    body = value.strip(" -·*•\t")
    if not body:
        return []
    items: list[str] = []
    for chunk in re.split(r"[、，,/;；|]+", body):
        candidate = chunk.strip(" -·*•\t")
        candidate = re.sub(r"^[\d一二三四五六七八九十]+[.、)）]\s*", "", candidate)
        candidate = re.sub(r"[（(][^）)]*[)）]$", "", candidate).strip()
        if 2 <= len(candidate) <= 40 and not candidate.startswith(("要求", "职责", "人数")):
            items.append(candidate)
    return items


def _extract_deadline(text: str, today: date) -> tuple[str | None, datetime | None]:
    for line in text.split("\n"):
        stripped = line.strip(" -·*•\t")
        if not any(key in stripped for key in DEADLINE_KEYS):
            continue
        if "招满" in stripped:
            return "招满为止", None
        found = _find_date(stripped, today)
        if found:
            return found.isoformat(), _to_datetime(found)
        return stripped[:100], None

    if "招满即止" in text or "招满为止" in text:
        return "招满为止", None
    return None, None


def _extract_published_at(lines: list[str], today: date) -> datetime | None:
    for line in lines[:12]:
        if "发布" not in line and "更新" not in line:
            continue
        found = _find_date(line, today)
        if found:
            return _to_datetime(found)
    return None


def _find_date(value: str, today: date) -> date | None:
    match = DATE_PATTERN.search(value)
    if match:
        return _safe_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    month_day = MONTH_DAY_PATTERN.search(value)
    if month_day:
        return _safe_date(today.year, int(month_day.group(1)), int(month_day.group(2)))
    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _to_datetime(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def _extract_apply_method(text: str) -> dict[str, object]:
    emails: list[str] = []
    for match in EMAIL_PATTERN.findall(text):
        if match not in emails:
            emails.append(match)
    links: list[str] = []
    for match in URL_PATTERN.findall(text):
        cleaned = match.rstrip(".")
        if "mp.weixin.qq.com" in cleaned and cleaned not in links:
            continue
        if cleaned not in links:
            links.append(cleaned)
    note = None
    for line in text.split("\n"):
        stripped = line.strip()
        if "截止" in stripped:
            continue
        if "网申" in stripped or "投递方式" in stripped or "简历投递" in stripped:
            note = stripped[:300]
            break
    return {
        "emails": emails[:5],
        "links": links[:5],
        "note": note,
    }


def _confidence(parsed: ParsedAnnouncement) -> dict[str, str]:
    return {
        "company_name": "high" if parsed.company_name else "low",
        "title": "high" if parsed.title else "low",
        "recruitment_type": "medium" if parsed.recruitment_type else "low",
        "target_cohort": "high" if parsed.target_cohort else "low",
        "locations": "high" if parsed.locations else "low",
        "positions": "medium" if parsed.positions else "low",
        "deadline": "high" if parsed.deadline_text else "low",
        "apply_method": (
            "high"
            if parsed.apply_method.get("emails") or parsed.apply_method.get("links")
            else "low"
        ),
    }


def positions_text(positions: list[str]) -> str | None:
    if not positions:
        return None
    return "、".join(positions)
