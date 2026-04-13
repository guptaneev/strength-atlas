from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx
from browser_use_sdk.v3 import AsyncBrowserUse

from atlas.browser_use.schemas import ExtractionPayload
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

    async def _run(self, prompt: str, **kwargs: Any):
        run = self._client.run(prompt, **kwargs)
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

    async def extract_url(self, url: str, model: str | None = None) -> BrowserUseResult:
        prompt = (
            "Open the URL and return a single JSON object only (no prose, no markdown, no explanations). "
            "Output keys: title, author, source_type, summary, main_text, raw_html, programs, claims. "
            "Use null when unknown and empty arrays when no items. "
            "For each program include: name, coach_name, days_per_week, specialization, experience_level, "
            "progression_type, split_type, summary, confidence in [0,1]. "
            "For each claim include: program_id (nullable), claim_type, raw_text, normalized_value, confidence in [0,1]. "
            "Do not mention file paths or that data was saved."
            f"\nURL: {url}"
        )
        result = await self._run(prompt, output_schema=ExtractionPayload, model=model)
        output = await self._resolve_extraction_output(result)
        return BrowserUseResult(
            output=output,
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

    async def stop_session(self, session_id: str, strategy: str = "task") -> None:
        await self._client.sessions.stop(session_id, strategy=strategy)

    async def close(self) -> None:
        await self._client.close()

    async def _resolve_extraction_output(self, result: Any) -> Any:
        output = getattr(result, "output", None)
        as_dict = _coerce_dict(output)
        if as_dict is not None:
            return as_dict

        session_id = getattr(result, "id", None)
        if isinstance(output, str) and session_id:
            workspace_json = await self._load_workspace_json_from_output(session_id, output)
            if workspace_json is not None:
                return workspace_json
        return output

    async def _load_workspace_json_from_output(self, session_id: str, output_text: str) -> dict[str, Any] | None:
        hinted_paths = re.findall(r"(/workspace/[^\s`\"']+\.json)", output_text)
        if not hinted_paths:
            return None

        files = await self._client.sessions.files(session_id, include_urls=True)
        matched = _find_workspace_file(files, hinted_paths)
        if matched is None:
            return None

        file_url = getattr(matched, "url", None)
        if not file_url:
            return None

        async with httpx.AsyncClient(timeout=30.0) as http:
            response = await http.get(file_url)
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError:
                return None
            return payload if isinstance(payload, dict) else None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        if isinstance(dumped, dict):
            return dumped
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
    return None


def _find_workspace_file(files_response: Any, hinted_paths: list[str]) -> Any | None:
    files = getattr(files_response, "files", None)
    if not isinstance(files, list):
        return None

    candidates = set()
    for path in hinted_paths:
        cleaned = path.strip()
        candidates.add(cleaned)
        candidates.add(cleaned.lstrip("/"))
        if cleaned.startswith("/workspace/"):
            rel = cleaned.removeprefix("/workspace/")
            candidates.add(rel)
            candidates.add(f"workspace/{rel}")

    for item in files:
        path = getattr(item, "path", None)
        if not isinstance(path, str):
            continue
        if path in candidates:
            return item
        with_prefix = f"/{path.lstrip('/')}"
        if with_prefix in candidates:
            return item
        if f"/workspace/{path.lstrip('/')}" in candidates:
            return item
    return None
