"""Job-search assistant chat (plan §5.6).

Only reachable with a bound ``chat`` provider: without credentials the endpoint
returns ``AI_CREDENTIALS_MISSING`` instead of inventing an answer.
"""

from __future__ import annotations

from time import perf_counter
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user_id
from app.core.errors import AppError, ErrorResponse
from app.domains.ai.client import require_chat_client
from app.domains.ai.schemas import AI_CONFIG_HEADER, AiCallError, decode_ai_config

router = APIRouter(prefix="/workspace/assistant", tags=["assistant"])

SYSTEM_PROMPT = (
    "你是 CareerPilot 的求职助手，只回答与职位筛选、投递进展、简历与面试准备相关的问题。"
    "回答保持简短、可执行，不编造用户没有提供的事实；与求职无关的话题请礼貌拒绝。"
)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    reply: str
    format: str
    model: str
    latency_ms: int


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        409: {"model": ErrorResponse, "description": "AI credentials missing"},
        502: {"model": ErrorResponse, "description": "Upstream model call failed"},
    },
)
def chat(
    payload: ChatRequest,
    _user_id: Annotated[str, Depends(get_current_user_id)],
    ai_config: Annotated[
        str | None, Header(alias=AI_CONFIG_HEADER, include_in_schema=False)
    ] = None,
) -> ChatResponse:
    config = decode_ai_config(ai_config)
    client = require_chat_client(config)
    assert config is not None  # narrowed by require_chat_client
    messages = [{"role": item.role, "content": item.content} for item in payload.history]
    messages.append({"role": "user", "content": payload.message})
    started = perf_counter()
    try:
        reply = client.complete(messages, system=SYSTEM_PROMPT)
    except AiCallError as exc:
        raise AppError(
            code="AI_CALL_FAILED",
            message="模型调用失败，请检查「AI 与设置」中的连接",
            status_code=502,
            details={"error": str(exc)[:300]},
        ) from None
    return ChatResponse(
        reply=reply,
        format=config.format,
        model=config.model,
        latency_ms=int((perf_counter() - started) * 1000),
    )
