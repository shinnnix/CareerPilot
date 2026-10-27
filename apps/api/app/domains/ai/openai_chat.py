"""OpenAI-compatible chat completions adapter (plan §5.3)."""

from __future__ import annotations

from app.domains.ai.schemas import AiCallError, AiConfig
from app.domains.ai.transport import post_json


class OpenAiChatClient:
    format = "openai"

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
            "messages": (
                [{"role": "system", "content": system}] if system else []
            )
            + list(messages),
            "temperature": self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
        }
        body = post_json(
            url=f"{self.config.base_url}/chat/completions",
            payload=payload,
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            fmt=self.format,
            model=self.config.model,
        )
        try:
            return str(body["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError):
            raise AiCallError("unexpected OpenAI response shape") from None
