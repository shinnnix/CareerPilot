"""Provider-agnostic LLM client factory (plan §5.3 / §5.3.5)."""

from __future__ import annotations

from typing import Protocol

from app.core.errors import AppError
from app.domains.ai.anthropic_chat import AnthropicChatClient
from app.domains.ai.openai_chat import OpenAiChatClient
from app.domains.ai.schemas import AiConfig


class AiClient(Protocol):
    format: str

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> str: ...


def build_client(config: AiConfig) -> AiClient:
    if config.format == "anthropic":
        return AnthropicChatClient(config)
    return OpenAiChatClient(config)


def require_chat_client(config: AiConfig | None) -> AiClient:
    """Chat must not silently degrade into a fake answer (plan §5.3.5)."""
    if config is None:
        raise AppError(
            code="AI_CREDENTIALS_MISSING",
            message="尚未配置 AI 凭据，无法进行对话",
            status_code=409,
            details={"hint": "打开「AI 与设置」绑定 chat 模型后再试"},
        )
    return build_client(config)
