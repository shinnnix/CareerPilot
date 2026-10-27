"""Optional LLM enhancement for rule-first extraction (plan §5.3.5).

The rule extractor always runs and always wins on conflicts. When an
``extraction`` provider is bound, the LLM pass only *fills the blanks*: any
failure, timeout or schema mismatch discards the LLM result and the caller
keeps ``llm_used=False``.
"""

from __future__ import annotations

import json
import re

from app.domains.ai.client import build_client
from app.domains.ai.schemas import AiCallError, AiConfig

# Fields the announcement parser produces and the LLM may help fill.
ANNOUNCEMENT_FIELDS = (
    "title",
    "company_name",
    "recruitment_type",
    "target_cohort",
    "locations",
    "positions",
    "deadline_text",
)

SYSTEM_PROMPT = (
    "你是一个校园招聘公告的信息抽取器。只输出一个 JSON 对象，不要解释。"
    "字段：title(字符串)、company_name(字符串)、recruitment_type(字符串，如 校招/实习/社招)、"
    "target_cohort(字符串，如 2026届)、locations(字符串数组)、positions(字符串数组)、"
    "deadline_text(字符串)。原文没有的信息填 null，不要猜测。"
)

MAX_EXCERPT = 6000
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _extract_json(reply: str) -> dict[str, object] | None:
    cleaned = _FENCE.sub("", reply).strip()
    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            return None
        cleaned = cleaned[start : end + 1]
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _is_blank(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict, tuple)):
        return len(value) == 0
    return False


def _coerce(key: str, value: object) -> object:
    if key in ("locations", "positions"):
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [item.strip() for item in re.split(r"[、,，;；/]", value) if item.strip()]
        return None
    if isinstance(value, (list, dict)):
        return None
    text = str(value).strip()
    return text or None


def enhance_announcement(
    parsed: dict[str, object],
    raw_text: str,
    config: AiConfig | None,
) -> tuple[dict[str, object], bool]:
    """Return ``(merged, llm_used)``; never raises.

    Merge policy (plan §2.7.1): the rule pass owns every field it filled. The LLM
    may only fill blanks; when both produced a *different* value the rule value
    is kept and the disagreement is recorded under ``alternatives`` with
    ``needs_review=True`` so the confirmation screen can show both candidates.
    """
    if config is None:
        return parsed, False

    client = build_client(config)
    excerpt = raw_text[:MAX_EXCERPT]
    try:
        reply = client.complete(
            [
                {
                    "role": "user",
                    "content": f"请从下面的招聘公告中抽取字段：\n\n{excerpt}",
                }
            ],
            system=SYSTEM_PROMPT,
            max_tokens=800,
        )
    except AiCallError:
        return parsed, False

    payload = _extract_json(reply)
    if payload is None:
        return parsed, False

    merged = dict(parsed)
    used = False
    alternatives: dict[str, dict[str, object]] = {}
    for key in ANNOUNCEMENT_FIELDS:
        llm_value = _coerce(key, payload.get(key))
        if _is_blank(llm_value):
            continue
        rule_value = merged.get(key)
        if _is_blank(rule_value):
            merged[key] = llm_value
            used = True
            continue
        if not _equivalent(rule_value, llm_value):
            alternatives[key] = {"rule": rule_value, "llm": llm_value}
    if alternatives:
        merged["needs_review"] = True
        merged["alternatives"] = alternatives
    return merged, used


def _equivalent(rule_value: object, llm_value: object) -> bool:
    """Loose comparison: equal after trimming, and sets for list fields."""

    if isinstance(rule_value, list) and isinstance(llm_value, list):
        return {str(item).strip() for item in rule_value} == {
            str(item).strip() for item in llm_value
        }
    return str(rule_value).strip() == str(llm_value).strip()
