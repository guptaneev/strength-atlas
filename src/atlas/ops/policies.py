from __future__ import annotations

from typing import Any

from atlas.ingest.retries import is_retryable_browser_use_error


def classify_error_code(exc: Exception) -> str:
    message = str(exc).lower()

    if "already has active crawl" in message:
        return "blocked_active_crawl"
    if isinstance(exc, TimeoutError) or "did not complete within" in message or "timeout" in message:
        return "timeout"
    if "schema_invalid" in message:
        return "schema_invalid"
    if "low_quality_output" in message:
        return "low_quality_output"
    if "no_programs_on_program_page" in message:
        return "no_programs_on_program_page"
    if "source not found" in message:
        return "source_not_found"
    if "event loop is closed" in message:
        return "event_loop_closed"
    if "foreign key constraint" in message or "violates foreign key" in message:
        return "fk_violation"
    if "atlas_browser_use_api_key is required" in message:
        return "config_missing_browser_use_api_key"
    if "atlas_database_url is required" in message:
        return "config_missing_database_url"
    if is_retryable_browser_use_error(exc):
        return "retryable_browser_use"
    return "terminal_error"


def error_kind_from_code(error_code: str | None) -> str | None:
    if not error_code:
        return None
    if error_code.startswith("blocked_"):
        return "blocked"
    if error_code in {
        "timeout",
        "retryable_browser_use",
    }:
        return "retryable"
    return "terminal"


def should_fail_run(summary: dict[str, Any], failure_rate_threshold: float) -> bool:
    totals = summary.get("totals", {})
    attempted = int(totals.get("succeeded", 0)) + int(totals.get("failed", 0))
    if attempted == 0:
        return False
    failure_rate = float(totals.get("failure_rate", 0.0))
    return failure_rate > failure_rate_threshold
