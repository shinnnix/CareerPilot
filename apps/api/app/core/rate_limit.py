import hashlib
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class _Window:
    started_at: float
    count: int


class FixedWindowRateLimiter:
    """Small single-process limiter; production replicas should use Redis."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._windows: dict[str, _Window] = {}
        self._lock = threading.Lock()

    def check(self, *, key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        now = self._clock()
        with self._lock:
            window = self._windows.get(key)
            if window is None or now - window.started_at >= window_seconds:
                self._windows[key] = _Window(started_at=now, count=1)
                self._discard_expired(now, window_seconds)
                return True, 0
            if window.count >= limit:
                retry_after = max(1, int(window_seconds - (now - window.started_at)) + 1)
                return False, retry_after
            window.count += 1
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()

    def _discard_expired(self, now: float, window_seconds: int) -> None:
        if len(self._windows) < 1_000:
            return
        self._windows = {
            key: value
            for key, value in self._windows.items()
            if now - value.started_at < window_seconds
        }


def anonymized_rate_limit_key(identity: str) -> str:
    return hashlib.blake2s(identity.encode("utf-8"), digest_size=12).hexdigest()


rate_limiter = FixedWindowRateLimiter()
