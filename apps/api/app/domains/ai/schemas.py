"""Wire-format config plumbing shared by both providers (plan §5.3)."""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.domains.ai.security import validate_base_url

AiFormat = Literal["openai", "anthropic"]
AiTask = Literal["chat", "extraction", "embedding", "rerank"]

AI_CONFIG_HEADER = "X-AI-Config"

# Anthropic has no embedding endpoint, so these tasks are OpenAI-only (§5.3.5).
OPENAI_ONLY_TASKS = ("embedding", "rerank")


class AiConfig(BaseModel):
    """Everything needed to call a provider once; never persisted server-side."""

    format: AiFormat = "openai"
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=200)
    api_key: str = Field(min_length=1, max_length=500)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=1024, ge=1, le=32000)

    @field_validator("base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def _guard_outbound_target(self) -> AiConfig:
        """Reject non-http(s), unresolvable and metadata/private targets (SSRF)."""

        self.base_url = validate_base_url(self.base_url)
        return self


class AiTestRequest(AiConfig):
    """Same shape as a live config; the test call is not persisted either."""


class AiTestResult(BaseModel):
    ok: bool
    format: AiFormat
    model: str | None = None
    latency_ms: int | None = None
    reply: str | None = None
    error: str | None = None
    hint: str | None = None


class AiMetrics(BaseModel):
    calls: int
    failures: int
    average_latency_ms: float
    by_format: dict[str, int]


class AiCallError(RuntimeError):
    """Raised when an upstream LLM call fails; callers fall back silently."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def decode_ai_config(raw_header: str | None) -> AiConfig | None:
    """Parse ``X-AI-Config`` (base64url JSON) into a validated config.

    Anything malformed yields ``None`` so the request continues with the
    deterministic path instead of failing.
    """
    if not raw_header:
        return None
    token = raw_header.strip()
    padding = "=" * (-len(token) % 4)
    try:
        decoded = base64.urlsafe_b64decode(token + padding)
        payload: Any = json.loads(decoded.decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return AiConfig.model_validate(payload)
    except ValidationError:
        return None


def encode_ai_config(config: AiConfig) -> str:
    """Inverse of :func:`decode_ai_config` (used by tests and scripts)."""
    payload = json.dumps(config.model_dump(), ensure_ascii=False, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def task_supported(fmt: str, task: str) -> bool:
    return not (fmt == "anthropic" and task in OPENAI_ONLY_TASKS)
