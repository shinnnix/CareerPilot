"""WeChat official-account article adapter (plan §2.7 B, minimal verification).

Scope is deliberately narrow and compliant:

* one URL at a time, provided by the user — no account history crawling;
* no login state, no cookies, no anti-bot circumvention;
* ``robots.txt`` is honoured by default (see :func:`_ensure_robots_allowed`);
* only the article body is converted to text and stored as a snapshot; the
  original link is always kept so the product links back to the source.
"""

from __future__ import annotations

import html
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.errors import AppError

ALLOWED_HOSTS = {"mp.weixin.qq.com"}
ROBOTS_URL = "https://mp.weixin.qq.com/robots.txt"
ROBOTS_TTL_SECONDS = 3600
MAX_BYTES = 2 * 1024 * 1024
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36 CareerPilot/0.1"
)
# Token used to match a site-specific ``User-agent`` group, if one exists.
ROBOTS_AGENT_TOKEN = "careerpilot"

_robots_cache: dict[str, tuple[float, str]] = {}


@dataclass
class ArticleSnapshot:
    url: str
    title: str | None
    account_name: str | None
    published_at: datetime | None
    text: str


def is_wechat_article(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.hostname in ALLOWED_HOSTS


def fetch_article(url: str, *, timeout: float = 12.0) -> ArticleSnapshot:
    if not is_wechat_article(url):
        raise AppError(
            code="JOB_IMPORT_FAILED",
            message="仅支持 mp.weixin.qq.com 的公众号文章链接",
            status_code=422,
            details={"url": url},
        )
    _ensure_robots_allowed(url, timeout=timeout)

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://mp.weixin.qq.com/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise _fetch_error(url, f"文章返回 HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise _fetch_error(url, "文章抓取失败，请检查网络或改用粘贴正文") from exc

    if len(raw) > MAX_BYTES:
        raise _fetch_error(url, "文章内容超过 2 MiB，请改用粘贴正文")
    page = raw.decode("utf-8", errors="replace")

    text = _extract_body(page)
    if len(text) < 40:
        raise _fetch_error(url, "未提取到文章正文，请改用粘贴正文")

    return ArticleSnapshot(
        url=url,
        title=_extract_title(page),
        account_name=_extract_account(page),
        published_at=_extract_published_at(page),
        text=text,
    )


def _fetch_error(url: str, message: str) -> AppError:
    return AppError(
        code="JOB_IMPORT_FAILED",
        message=message,
        status_code=422,
        details={"url": url},
    )


# ---------------------------------------------------------------------------
# robots.txt (RFC 9309 subset: user-agent groups, Allow/Disallow, ``$`` anchor)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RobotsRule:
    allow: bool
    pattern: str


def parse_robots(text: str) -> list[RobotsRule]:
    """Rules that apply to CareerPilot: the ``*`` group plus any named group."""

    groups: list[tuple[set[str], list[RobotsRule]]] = []
    agents: set[str] = set()
    rules: list[RobotsRule] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            if agents:
                groups.append((agents, rules))
                agents, rules = set(), []
            agents.add(value.lower())
        elif field in {"allow", "disallow"} and agents:
            if not value:
                # ``Disallow:`` with an empty value means "nothing disallowed".
                continue
            rules.append(RobotsRule(allow=field == "allow", pattern=value))
    if agents:
        groups.append((agents, rules))

    selected: list[RobotsRule] = []
    for group_agents, group_rules in groups:
        if "*" in group_agents or any(
            ROBOTS_AGENT_TOKEN in agent for agent in group_agents
        ):
            selected.extend(group_rules)
    return selected


def is_allowed_by_robots(path: str, rules: list[RobotsRule]) -> bool:
    """Longest match wins; ties go to ``Allow`` (RFC 9309 §2.2.2)."""

    target = path or "/"
    best_length = -1
    allowed = True
    for rule in rules:
        pattern = rule.pattern
        anchored = pattern.endswith("$")
        candidate = pattern[:-1] if anchored else pattern
        matches = target == candidate if anchored else target.startswith(candidate)
        if not matches:
            continue
        length = len(candidate)
        if length > best_length or (length == best_length and rule.allow):
            best_length = length
            allowed = rule.allow
    return allowed


def _robots_rules(timeout: float) -> list[RobotsRule]:
    cached = _robots_cache.get(ROBOTS_URL)
    now = time.time()
    if cached is not None and now - cached[0] < ROBOTS_TTL_SECONDS:
        return parse_robots(cached[1])

    robots_timeout = max(1.0, min(timeout, 8.0))
    try:
        request = urllib.request.Request(
            ROBOTS_URL, headers={"User-Agent": USER_AGENT, "Accept": "text/plain"}
        )
        with urllib.request.urlopen(request, timeout=robots_timeout) as response:
            text = response.read(64 * 1024).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        # An explicit denial (401/403) is treated as "disallow everything";
        # a missing robots file (404) means "no restriction".
        text = "User-agent: *\nDisallow: /\n" if exc.code in {401, 403} else ""
    except (urllib.error.URLError, TimeoutError, OSError):
        # Unreachable robots: do not block the user, log nothing sensitive.
        text = ""
    _robots_cache[ROBOTS_URL] = (now, text)
    return parse_robots(text)


def _ensure_robots_allowed(url: str, *, timeout: float) -> None:
    if not get_settings().wechat_respect_robots:
        return
    path = urllib.parse.urlsplit(url).path or "/"
    if is_allowed_by_robots(path, _robots_rules(timeout)):
        return
    raise AppError(
        code="JOB_IMPORT_ROBOTS_DISALLOWED",
        message=(
            "该站点的 robots.txt 不允许抓取文章页，请改用「粘贴正文」导入这条公告。"
            "若你已从权利方获得抓取授权，可由管理员设置 "
            "CAREERPILOT_WECHAT_RESPECT_ROBOTS=false 关闭该校验。"
        ),
        status_code=422,
        details={"url": url, "path": path, "robots_url": ROBOTS_URL},
    )


def _extract_body(page: str) -> str:
    container = re.search(
        r'<div[^>]+id="js_content"[^>]*>(.*?)</div>\s*(?:<script|<div[^>]+id="js_pc_qr_code")',
        page,
        re.DOTALL,
    )
    fragment = container.group(1) if container else page
    fragment = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragment, flags=re.DOTALL | re.IGNORECASE)
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"</(p|section|div|li|h[1-6])>", "\n", fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    text = html.unescape(fragment)
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    lines = [line.strip() for line in text.split("\n")]
    cleaned = "\n".join(line for line in lines if line)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _extract_title(page: str) -> str | None:
    for pattern in (
        r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
        r'<h1[^>]*id="activity-name"[^>]*>(.*?)</h1>',
        r"var\s+msg_title\s*=\s*['\"](.+?)['\"]",
    ):
        match = re.search(pattern, page, re.DOTALL | re.IGNORECASE)
        if match:
            value = html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
            if value:
                return value[:300]
    return None


def _extract_account(page: str) -> str | None:
    for pattern in (
        r'<a[^>]+id="js_name"[^>]*>(.*?)</a>',
        r'var\s+nickname\s*=\s*["\'](.+?)["\']',
        r'<meta[^>]+property="og:article:author"[^>]+content="([^"]+)"',
    ):
        match = re.search(pattern, page, re.DOTALL | re.IGNORECASE)
        if match:
            value = html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
            if value:
                return value[:200]
    return None


def _extract_published_at(page: str) -> datetime | None:
    match = re.search(r'var\s+ct\s*=\s*"?(\d{10})"?', page)
    if match:
        return datetime.fromtimestamp(int(match.group(1)), tz=timezone.utc)
    meta = re.search(
        r'<meta[^>]+property="article:published_time"[^>]+content="([^"]+)"', page
    )
    if meta:
        try:
            return datetime.fromisoformat(meta.group(1).replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
