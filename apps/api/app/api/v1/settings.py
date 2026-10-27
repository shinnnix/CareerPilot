"""AI settings endpoints (plan §5.3).

Every endpoint requires an authenticated caller: ``/ai/test`` proxies an
outbound request from the API process, so leaving it open would make the local
API an unauthenticated SSRF/debug proxy.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status

from app.api.dependencies import get_current_user_id
from app.core.errors import ErrorResponse
from app.domains.ai.metrics import ai_metrics
from app.domains.ai.schemas import (
    AI_CONFIG_HEADER,
    AiMetrics,
    AiTestRequest,
    AiTestResult,
    decode_ai_config,
)
from app.domains.ai.service import AiSettingsService

router = APIRouter(prefix="/workspace/settings", tags=["settings"])

_HEADER = Annotated[str | None, Header(alias=AI_CONFIG_HEADER, include_in_schema=False)]
_User = Annotated[str, Depends(get_current_user_id)]


def _service() -> AiSettingsService:
    return AiSettingsService()


@router.post(
    "/ai/test",
    response_model=AiTestResult,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def test_ai_connection(payload: AiTestRequest, _user_id: _User) -> AiTestResult:
    """Probe a provider through the local API to avoid browser CORS issues."""
    return _service().test(payload)


@router.get(
    "/ai/metrics",
    response_model=AiMetrics,
    responses={401: {"model": ErrorResponse}},
)
def ai_call_metrics(_user_id: _User) -> AiMetrics:
    return _service().metrics()


@router.get(
    "/ai/echo",
    responses={401: {"model": ErrorResponse}},
)
def echo_ai_config(_user_id: _User, header: _HEADER = None) -> dict[str, object]:
    """Confirm what the server understood from ``X-AI-Config`` (never the key)."""
    config = decode_ai_config(header)
    if config is None:
        return {"configured": False}
    return {
        "configured": True,
        "format": config.format,
        "base_url": config.base_url,
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }


@router.delete(
    "/ai/metrics",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}},
)
def reset_ai_metrics(_user_id: _User) -> Response:
    ai_metrics.reset()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
