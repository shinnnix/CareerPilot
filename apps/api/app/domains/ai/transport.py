"""Bounded HTTP transport for LLM calls (timeout + retries + telemetry)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from app.core.observability import log_ai_call
from app.domains.ai.metrics import ai_metrics
from app.domains.ai.schemas import AiCallError

TIMEOUT_SECONDS = 15
# Two retries with exponential backoff (§5.3.5).
RETRY_DELAYS = (0.0, 0.5, 1.0)


def post_json(
    *,
    url: str,
    payload: dict[str, object],
    headers: dict[str, str],
    fmt: str,
    model: str,
) -> dict[str, object]:
    """POST JSON with a bounded timeout, two retries and call telemetry."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_error = "unknown error"
    for delay in RETRY_DELAYS:
        if delay:
            time.sleep(delay)
        started = time.perf_counter()
        request = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json", **headers},
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}: {_safe_detail(exc)}"
            latency_ms = int((time.perf_counter() - started) * 1000)
            ai_metrics.record(fmt=fmt, ok=False, latency_ms=latency_ms)
            log_ai_call(format=fmt, model=model, ok=False, latency_ms=latency_ms, status=exc.code)
            # 4xx other than 429 will not succeed on retry.
            if 400 <= exc.code < 500 and exc.code != 429:
                raise AiCallError(last_error, status_code=exc.code) from None
            continue
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            latency_ms = int((time.perf_counter() - started) * 1000)
            ai_metrics.record(fmt=fmt, ok=False, latency_ms=latency_ms)
            log_ai_call(
                format=fmt,
                model=model,
                ok=False,
                latency_ms=latency_ms,
                error=type(exc).__name__,
            )
            continue

        latency_ms = int((time.perf_counter() - started) * 1000)
        ai_metrics.record(fmt=fmt, ok=True, latency_ms=latency_ms)
        log_ai_call(format=fmt, model=model, ok=True, latency_ms=latency_ms)
        if not isinstance(body, dict):
            raise AiCallError("unexpected response shape")
        return body
    raise AiCallError(last_error)


def _safe_detail(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8", "replace")
    except (OSError, ValueError, AttributeError):  # pragma: no cover - defensive
        return "no body"
    return raw[:200].replace("\n", " ")
