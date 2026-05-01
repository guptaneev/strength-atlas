from __future__ import annotations


class AuthError(Exception):
    pass


class QuotaExceededError(Exception):
    def __init__(self, *, limit: int, used: int, remaining: int, contact_url: str) -> None:
        super().__init__("ask_quota_exceeded")
        self.limit = limit
        self.used = used
        self.remaining = remaining
        self.contact_url = contact_url


class RateLimitExceededError(Exception):
    def __init__(self, *, key: str, retry_after_seconds: int) -> None:
        super().__init__("rate_limit_exceeded")
        self.key = key
        self.retry_after_seconds = retry_after_seconds
