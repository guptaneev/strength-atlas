from __future__ import annotations

import pytest

from atlas.api.errors import RateLimitExceededError
from atlas.api.rate_limit import InMemoryRateLimiter, RateLimitRule


def test_in_memory_rate_limiter_blocks_after_limit() -> None:
    limiter = InMemoryRateLimiter()
    rule = RateLimitRule(window_seconds=60, max_requests=2)
    limiter.check("k", rule)
    limiter.check("k", rule)
    with pytest.raises(RateLimitExceededError):
        limiter.check("k", rule)
