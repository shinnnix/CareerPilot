import hashlib
import json
import logging

request_logger = logging.getLogger("careerpilot.requests")

# Never let these reach a log line, whatever the caller passes (plan §5.3).
SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "x-ai-config",
        "token",
        "access_token",
        "password",
        "prompt",
        "messages",
        "content",
    }
)
MASK = "***"


def configure_observability() -> None:
    if not request_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        request_logger.addHandler(handler)
    request_logger.setLevel(logging.INFO)
    request_logger.propagate = False


def hash_identifier(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def redact_mapping(payload: dict[str, object]) -> dict[str, object]:
    """Recursively mask credential- and prompt-bearing keys."""
    redacted: dict[str, object] = {}
    for key, value in payload.items():
        if key.lower() in SENSITIVE_KEYS:
            redacted[key] = MASK
        elif isinstance(value, dict):
            redacted[key] = redact_mapping(value)
        elif isinstance(value, list):
            redacted[key] = [MASK if isinstance(item, str) else item for item in value]
        else:
            redacted[key] = value
    return redacted


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key: (MASK if key.lower() in SENSITIVE_KEYS else value)
        for key, value in headers.items()
    }


def log_request(**fields: object) -> None:
    request_logger.info(
        json.dumps(redact_mapping(fields), ensure_ascii=False, separators=(",", ":"))
    )


def log_ai_call(**fields: object) -> None:
    """Telemetry for one LLM call: format/model/latency only."""
    request_logger.info(
        json.dumps(
            redact_mapping({"event": "ai_call", **fields}),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
