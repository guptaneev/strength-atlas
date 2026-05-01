from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

from atlas.api.errors import RateLimitExceededError


@dataclass(frozen=True)
class RateLimitRule:
    window_seconds: int
    max_requests: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[str, deque[float]] = {}

    def check(self, key: str, rule: RateLimitRule) -> None:
        now = time.time()
        window = max(1, int(rule.window_seconds))
        max_requests = max(1, int(rule.max_requests))
        cutoff = now - window
        with self._lock:
            queue = self._buckets.setdefault(key, deque())
            while queue and queue[0] < cutoff:
                queue.popleft()
            if len(queue) >= max_requests:
                retry_after = int(max(1.0, window - (now - queue[0])))
                raise RateLimitExceededError(key=key, retry_after_seconds=retry_after)
            queue.append(now)
