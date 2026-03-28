from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db.models import CrawlJob, Domain, Source

ACTIVE_CRAWL_STATUSES = ("pending", "running")


def get_active_crawl_for_domain(session: Session, domain: str) -> CrawlJob | None:
    # Source-linked crawl jobs (extract/refresh)
    source_linked = session.execute(
        select(CrawlJob)
        .join(Source, CrawlJob.source_id == Source.id)
        .join(Domain, Source.domain_id == Domain.id)
        .where(
            Domain.domain == domain,
            CrawlJob.status.in_(ACTIVE_CRAWL_STATUSES),
        )
        .order_by(CrawlJob.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if source_linked is not None:
        return source_linked

    # Discover crawl jobs have no source_id; match by target_url host.
    discover_jobs = session.execute(
        select(CrawlJob)
        .where(
            CrawlJob.source_id.is_(None),
            CrawlJob.status.in_(ACTIVE_CRAWL_STATUSES),
        )
        .order_by(CrawlJob.started_at.desc())
    ).scalars().all()
    for job in discover_jobs:
        host = urlparse(job.target_url or "").netloc.lower()
        if host == domain or host.endswith(f".{domain}"):
            return job
    return None
