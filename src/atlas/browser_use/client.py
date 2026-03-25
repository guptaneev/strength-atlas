from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from browser_use_sdk.v3 import AsyncBrowserUse

from atlas.config.settings import get_settings


@dataclass
class BrowserUseResult:
    output: Any
    session_id: str | None
    live_url: str | None
    status: str | None
    total_cost_usd: float | None


class BrowserUseClient:
    def __init__(self, poll_timeout_seconds: float | None = None) -> None:
        settings = get_settings()
        if not settings.browser_use_api_key:
            raise RuntimeError("ATLAS_BROWSER_USE_API_KEY is required")
        self._client = AsyncBrowserUse(api_key=settings.browser_use_api_key)
        self._poll_timeout_seconds = poll_timeout_seconds or settings.browser_use_poll_timeout_seconds

    async def _run(self, prompt: str):
        run = self._client.run(prompt)
        # browser-use-sdk v3 doesn't currently expose timeout in run(); this
        # sets the AsyncSessionRun poll timeout to avoid hardcoded 300s failures.
        if hasattr(run, "_timeout"):
            run._timeout = self._poll_timeout_seconds
        return await run

    async def discover_urls(self, domain: str, seed_urls: list[str]) -> BrowserUseResult:
        prompt = (
            "Find program-related pages on this domain. "
            "Return a JSON array of candidate URLs only, no extra text."
            f"\nDomain: {domain}\nSeed URLs:\n"
            + "\n".join(seed_urls)
        )
        result = await self._run(prompt)
        return BrowserUseResult(
            output=result.output,
            session_id=getattr(result, "id", None),
            live_url=getattr(result, "live_url", None),
            status=getattr(result, "status", None),
            total_cost_usd=_to_float(getattr(result, "total_cost_usd", None)),
        )

    async def extract_url(self, url: str) -> BrowserUseResult:
        prompt = (
            "Open the URL and extract: title, author if present, main text, "
            "and any program-related metadata. Return JSON only."
            f"\nURL: {url}"
        )
        result = await self._run(prompt)
        return BrowserUseResult(
            output=result.output,
            session_id=getattr(result, "id", None),
            live_url=getattr(result, "live_url", None),
            status=getattr(result, "status", None),
            total_cost_usd=_to_float(getattr(result, "total_cost_usd", None)),
        )

    async def refresh_source(self, source_id: str) -> BrowserUseResult:
        prompt = (
            "Refresh this source by reloading the URL and re-extracting the same fields "
            "as the initial extraction. Return JSON only."
            f"\nSource ID: {source_id}"
        )
        result = await self._run(prompt)
        return BrowserUseResult(
            output=result.output,
            session_id=getattr(result, "id", None),
            live_url=getattr(result, "live_url", None),
            status=getattr(result, "status", None),
            total_cost_usd=_to_float(getattr(result, "total_cost_usd", None)),
        )


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
