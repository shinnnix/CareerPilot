import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ContentSecurityResult:
    prompt_injection_detected: bool
    flags: list[str]


_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction_override",
        re.compile(
            r"(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?"
            r"|(?:忽略|无视|忘记)(?:以上|之前|先前|所有).{0,12}(?:指令|要求|提示词)",
            re.IGNORECASE,
        ),
    ),
    (
        "prompt_exfiltration",
        re.compile(
            r"(?:reveal|show|print|repeat).{0,24}(?:system|developer)\s+(?:prompt|message)"
            r"|(?:泄露|显示|输出|复述).{0,20}(?:系统|开发者).{0,8}(?:提示词|消息|指令)",
            re.IGNORECASE,
        ),
    ),
    (
        "tool_or_data_exfiltration",
        re.compile(
            r"(?:call|invoke|use).{0,20}(?:tool|function).{0,35}(?:secret|token|password|credential)"
            r"|(?:调用|使用).{0,16}(?:工具|函数).{0,30}(?:密钥|令牌|密码|凭证)",
            re.IGNORECASE,
        ),
    ),
    (
        "role_impersonation",
        re.compile(
            r"(?:you are now|act as).{0,30}(?:system|developer|administrator)"
            r"|(?:你现在是|扮演).{0,24}(?:系统|开发者|管理员)",
            re.IGNORECASE,
        ),
    ),
)


def scan_untrusted_content(text: str) -> ContentSecurityResult:
    """Flag likely prompt injection without executing or rewriting document text.

    This deterministic layer is intentionally conservative and auditable. It is a
    guardrail, not a proof that unflagged text is safe.
    """

    flags = [name for name, pattern in _RULES if pattern.search(text)]
    return ContentSecurityResult(bool(flags), flags)
