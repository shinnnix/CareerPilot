"""Anthropic Messages adapter (plan §5.3).

Differences from the OpenAI format: ``system`` is a top-level field,
``max_tokens`` is required, auth uses ``x-api-key`` plus a version header, and
there is no embedding endpoint.
"""

from __future__ import annotations

from app.domains.ai.schemas import AiCallError, AiConfig
from app.domains.ai.transport import post_json

ANTHROPIC_VERSION = "2023-06-01"


class AnthropicChatClient:
    format = "anthropic"

    def __init__(self, config: AiConfig) -> None:
        self.config = config

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "model": self.config.model,
            "messages": [
                {"role": item["role"], "content": item["content"]}
                for item in messages
                if item.get("role") != "system"
            ],
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        if system:
            payload["system"] = system
        body = post_json(
            url=f"{self.config.base_url}/v1/messages",
            payload=payload,
            headers={
                "x-api-key": self.config.api_key,
                "anthropic-version": ANTHROPIC_VERSION,
            },
            fmt=self.format,
            model=self.config.model,
        )
        try:
            blocks = body["content"]
            if not isinstance(blocks, list):
                raise TypeError
            texts = [
                str(block.get("text", ""))
                for block in blocks
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            if not texts:
                raise KeyError("content")
            return "\n".join(texts)
        except (KeyError, IndexError, TypeError):
            raise AiCallError("unexpected Anthropic response shape") from None
