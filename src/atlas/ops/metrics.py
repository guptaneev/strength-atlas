from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def build_run_summary(
    *,
    run_id: str,
    started_at: str,
    completed_at: str,
    duration_seconds: float,
    policy: dict[str, Any],
    domains_scanned: int,
    sources_queued: int,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    source_items = [it for it in items if it.get("item_type") in {"extract_pending", "refresh_empty"}]

    succeeded = len([it for it in source_items if it.get("status") == "succeeded"])
    failed = len([it for it in source_items if it.get("status") == "failed"])
    blocked = len([it for it in source_items if it.get("status") == "blocked"])
    skipped = len([it for it in source_items if it.get("status") == "skipped"])
    processed = succeeded + failed + blocked + skipped

    attempted = succeeded + failed
    failure_rate = (failed / attempted) if attempted else 0.0

    programs_created_total = int(
        sum(int(it.get("program_count", 0) or 0) for it in source_items if it.get("status") == "succeeded")
    )
    program_yield_rate = (programs_created_total / succeeded) if succeeded else 0.0

    confidence_values = [
        float(it.get("parse_confidence"))
        for it in source_items
        if it.get("status") == "succeeded" and it.get("parse_confidence") is not None
    ]
    avg_parse_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else None

    empty_program_successes = len(
        [
            it
            for it in source_items
            if it.get("mode") == "refresh_empty" and it.get("status") == "succeeded" and int(it.get("program_count", 0) or 0) > 0
        ]
    )

    retry_events = int(sum(int(it.get("retry_count", 0) or 0) for it in items))
    timeout_count = len([it for it in items if it.get("error_code") == "timeout"])

    error_counter = Counter(
        str(it.get("error_code"))
        for it in items
        if it.get("error_code") and it.get("status") in {"failed", "blocked"}
    )
    top_error_codes = [{"code": code, "count": count} for code, count in error_counter.most_common(5)]

    browser_use_cost_usd_total = float(
        sum(float(it.get("cost_usd", 0.0) or 0.0) for it in items if it.get("cost_usd") is not None)
    )
    avg_cost_per_success = (browser_use_cost_usd_total / succeeded) if succeeded else None

    domain_buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "queued": 0,
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "blocked": 0,
            "skipped": 0,
            "retry_events": 0,
            "browser_use_cost_usd_total": 0.0,
        }
    )
    for it in source_items:
        domain = str(it.get("domain") or "unknown")
        bucket = domain_buckets[domain]
        bucket["queued"] += 1
        bucket["retry_events"] += int(it.get("retry_count", 0) or 0)
        bucket["browser_use_cost_usd_total"] += float(it.get("cost_usd", 0.0) or 0.0)

        status = str(it.get("status") or "")
        if status in {"succeeded", "failed", "blocked", "skipped"}:
            bucket[status] += 1
            bucket["processed"] += 1

    by_domain = [
        {"domain": domain, **values}
        for domain, values in sorted(domain_buckets.items(), key=lambda kv: kv[0])
    ]

    return {
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "policy": policy,
        "totals": {
            "domains_scanned": domains_scanned,
            "sources_queued": sources_queued,
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "blocked": blocked,
            "skipped": skipped,
            "programs_created_total": programs_created_total,
            "program_yield_rate": program_yield_rate,
            "avg_parse_confidence": avg_parse_confidence,
            "empty_program_successes": empty_program_successes,
            "failure_rate": failure_rate,
            "retry_events": retry_events,
            "timeout_count": timeout_count,
            "top_error_codes": top_error_codes,
            "browser_use_cost_usd_total": browser_use_cost_usd_total,
            "avg_cost_per_success": avg_cost_per_success,
            "duration_seconds": duration_seconds,
        },
        "by_domain": by_domain,
        "errors": top_error_codes,
        "items": items,
    }


def summarize_run_history(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        return {
            "runs_analyzed": 0,
            "latest_run_id": None,
            "latest_completed_at": None,
            "totals": {
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "blocked": 0,
                "skipped": 0,
                "browser_use_cost_usd_total": 0.0,
                "duration_seconds_total": 0.0,
            },
            "avg_failure_rate": 0.0,
            "max_failure_rate": 0.0,
            "top_error_codes": [],
        }

    processed = 0
    succeeded = 0
    failed = 0
    blocked = 0
    skipped = 0
    total_cost = 0.0
    total_duration = 0.0
    failure_rates: list[float] = []
    error_counter: Counter[str] = Counter()

    for run in runs:
        totals = run.get("totals", {})
        processed += int(totals.get("processed", 0) or 0)
        succeeded += int(totals.get("succeeded", 0) or 0)
        failed += int(totals.get("failed", 0) or 0)
        blocked += int(totals.get("blocked", 0) or 0)
        skipped += int(totals.get("skipped", 0) or 0)
        total_cost += float(totals.get("browser_use_cost_usd_total", 0.0) or 0.0)
        total_duration += float(totals.get("duration_seconds", 0.0) or 0.0)
        failure_rates.append(float(totals.get("failure_rate", 0.0) or 0.0))

        for error in run.get("errors", []):
            code = error.get("code")
            count = int(error.get("count", 0) or 0)
            if code:
                error_counter[str(code)] += count

    latest = runs[-1]
    return {
        "runs_analyzed": len(runs),
        "latest_run_id": latest.get("run_id"),
        "latest_completed_at": latest.get("completed_at"),
        "totals": {
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "blocked": blocked,
            "skipped": skipped,
            "browser_use_cost_usd_total": total_cost,
            "duration_seconds_total": total_duration,
        },
        "avg_failure_rate": (sum(failure_rates) / len(failure_rates)) if failure_rates else 0.0,
        "max_failure_rate": max(failure_rates) if failure_rates else 0.0,
        "top_error_codes": [
            {"code": code, "count": count} for code, count in error_counter.most_common(5)
        ],
    }
