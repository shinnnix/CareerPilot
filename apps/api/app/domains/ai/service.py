"""AI settings: connection test and metrics (plan §5.3).

Credentials arrive per request in ``X-AI-Config`` and are used in memory only —
nothing here writes to the database or to the logs.
"""

from __future__ import annotations

from time import perf_counter

from app.domains.ai.client import build_client
from app.domains.ai.metrics import ai_metrics
from app.domains.ai.schemas import (
    AiCallError,
    AiConfig,
    AiMetrics,
    AiTestRequest,
    AiTestResult,
)


class AiSettingsService:
    def test(self, payload: AiTestRequest) -> AiTestResult:
        config = AiConfig(**payload.model_dump())
        client = build_client(config)
        started = perf_counter()
        try:
            reply = client.complete(
                [{"role": "user", "content": "ping"}],
                max_tokens=16,
            )
        except AiCallError as exc:
            return AiTestResult(
                ok=False,
                format=config.format,
                model=config.model,
                latency_ms=int((perf_counter() - started) * 1000),
                error=str(exc),
                hint=_hint_for(config, str(exc)),
            )
        return AiTestResult(
            ok=True,
            format=config.format,
            model=config.model,
            latency_ms=int((perf_counter() - started) * 1000),
            reply=reply[:200],
        )

    @staticmethod
    def metrics() -> AiMetrics:
        return ai_metrics.snapshot()


def _hint_for(config: AiConfig, error: str) -> str:
    lowered = error.lower()
    if "401" in error or "403" in error or "api key" in lowered or "unauthorized" in lowered:
        return "凭据被拒绝：检查 api_key 是否有效、是否与所选格式匹配"
    if "404" in error:
        suffix = "/chat/completions" if config.format == "openai" else "/v1/messages"
        return f"端点不存在：base_url 应能拼出 {suffix}，不要重复带 /v1"
    if "timeout" in lowered or "timed out" in lowered:
        return "连接超时：检查 base_url 是否可达（本机代理需允许该域名）"
    return "检查 base_url、模型名与网络连通性"
