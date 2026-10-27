"""In-process call counters for LLM usage (plan §5.3.5).

Counts only: never prompts, never keys, never model output.
"""

from __future__ import annotations

from threading import Lock

from app.domains.ai.schemas import AiMetrics


class _AiMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._calls = 0
        self._failures = 0
        self._latency_total = 0
        self._by_format: dict[str, int] = {}

    def record(self, *, fmt: str, ok: bool, latency_ms: int) -> None:
        with self._lock:
            self._calls += 1
            self._latency_total += max(latency_ms, 0)
            self._by_format[fmt] = self._by_format.get(fmt, 0) + 1
            if not ok:
                self._failures += 1

    def snapshot(self) -> AiMetrics:
        with self._lock:
            calls = self._calls
            average = round(self._latency_total / calls, 2) if calls else 0.0
            return AiMetrics(
                calls=calls,
                failures=self._failures,
                average_latency_ms=average,
                by_format=dict(self._by_format),
            )

    def reset(self) -> None:
        with self._lock:
            self._calls = 0
            self._failures = 0
            self._latency_total = 0
            self._by_format.clear()


ai_metrics = _AiMetrics()
