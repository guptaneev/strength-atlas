from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db.models import Domain, Source


def build_backlog_report(
    session: Session,
    *,
    domains: list[str] | None = None,
    stale_after_days: int = 14,
    pending_sample_size: int = 5,
) -> dict[str, Any]:
    target_domains = {d.strip().lower() for d in (domains or []) if d and d.strip()}
    rows = session.execute(select(Source, Domain.domain).join(Domain, Domain.id == Source.domain_id)).all()
    now = dt.datetime.now(dt.UTC)
    stale_cutoff = now - dt.timedelta(days=max(1, stale_after_days))

    by_domain: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "sources_total": 0,
            "pending": 0,
            "succeeded": 0,
            "failed": 0,
            "stale_succeeded": 0,
            "pending_samples": [],
        }
    )

    for source, domain in rows:
        if target_domains and domain not in target_domains:
            continue
        bucket = by_domain[domain]
        bucket["sources_total"] += 1
        status = str(source.status or "")
        if status == "pending":
            bucket["pending"] += 1
            if len(bucket["pending_samples"]) < pending_sample_size:
                bucket["pending_samples"].append(
                    {
                        "source_id": source.id,
                        "canonical_url": source.canonical_url,
                    }
                )
        elif status == "succeeded":
            bucket["succeeded"] += 1
            if source.last_crawled_at is None or source.last_crawled_at < stale_cutoff:
                bucket["stale_succeeded"] += 1
        elif status == "failed":
            bucket["failed"] += 1

    domain_rows = [{"domain": d, **stats} for d, stats in sorted(by_domain.items(), key=lambda row: row[0])]
    totals = {
        "domains_count": len(domain_rows),
        "sources_total": sum(row["sources_total"] for row in domain_rows),
        "pending": sum(row["pending"] for row in domain_rows),
        "succeeded": sum(row["succeeded"] for row in domain_rows),
        "failed": sum(row["failed"] for row in domain_rows),
        "stale_succeeded": sum(row["stale_succeeded"] for row in domain_rows),
    }
    return {
        "generated_at": now.isoformat(),
        "stale_after_days": max(1, stale_after_days),
        "totals": totals,
        "by_domain": domain_rows,
    }
