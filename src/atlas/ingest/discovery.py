from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.browser_use.client import BrowserUseClient
from atlas.db.models import CrawlJob, Domain, Source


@dataclass(frozen=True)
class DiscoveryResult:
    created_sources: list[Source]
    skipped_urls: list[str]
    crawl_job: CrawlJob | None = None
    candidate_urls: list[str] | None = None


def canonicalize_url(url: str) -> str:
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    if not parsed.netloc and parsed.path and "://" not in cleaned:
        parsed = urlparse(f"https://{cleaned}")
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunparse((scheme, netloc, path, "", "", ""))


def is_domain_allowlisted(session: Session, domain: str) -> bool:
    stmt = select(Domain).where(
        Domain.domain == domain,
        Domain.allowlisted.is_(True),
        Domain.paused.is_(False),
    )
    return session.execute(stmt).scalar_one_or_none() is not None


def is_duplicate_canonical(session: Session, canonical_url: str) -> bool:
    stmt = select(Source).where(Source.canonical_url == canonical_url)
    return session.execute(stmt).scalar_one_or_none() is not None


def create_sources_from_urls(
    session: Session,
    domain: str,
    candidate_urls: Iterable[str],
) -> DiscoveryResult:
    created: list[Source] = []
    skipped: list[str] = []

    for url in candidate_urls:
        canonical = canonicalize_url(url)
        if is_duplicate_canonical(session, canonical):
            skipped.append(canonical)
            continue
        domain_row = session.execute(
            select(Domain).where(Domain.domain == domain)
        ).scalar_one_or_none()
        if domain_row is None:
            skipped.append(canonical)
            continue
        source = Source(
            url=url,
            canonical_url=canonical,
            domain_id=domain_row.id,
            status="pending",
        )
        session.add(source)
        created.append(source)

    session.commit()
    return DiscoveryResult(created_sources=created, skipped_urls=skipped)


async def discover_and_create_sources(
    session: Session,
    client: BrowserUseClient,
    domain: str,
    seed_urls: list[str],
) -> DiscoveryResult:
    crawl_job = CrawlJob(
        job_type="discover",
        source_id=None,
        target_url=f"https://{domain}",
        status="pending",
        started_at=dt.datetime.now(dt.UTC),
    )
    session.add(crawl_job)
    session.commit()

    crawl_job.status = "running"
    session.commit()

    try:
        result = await client.discover_urls(domain=domain, seed_urls=seed_urls)
        crawl_job.browser_use_session_id = result.session_id
        crawl_job.browser_use_live_url = result.live_url
        crawl_job.browser_use_cost_usd = result.total_cost_usd

        candidate_urls = parse_candidate_urls(result.output)
        candidate_urls = [u for u in candidate_urls if is_url_in_domain(u, domain)]
        created = create_sources_from_urls(session, domain, candidate_urls)

        crawl_job.status = "succeeded"
        crawl_job.completed_at = dt.datetime.now(dt.UTC)
        session.commit()
        return DiscoveryResult(
            created_sources=created.created_sources,
            skipped_urls=created.skipped_urls,
            crawl_job=crawl_job,
            candidate_urls=candidate_urls,
        )
    except Exception as exc:
        if hasattr(session, "rollback"):
            session.rollback()
        crawl_job.status = "failed"
        crawl_job.error_message = str(exc)
        crawl_job.completed_at = dt.datetime.now(dt.UTC)
        session.commit()
        raise


def parse_candidate_urls(output: Any) -> list[str]:
    urls: list[str] = []

    def _collect(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                _collect(item)
            return
        if isinstance(value, dict):
            for key in ("urls", "candidate_urls", "links"):
                if key in value:
                    _collect(value[key])
            return
        if isinstance(value, str):
            maybe_json = _try_parse_json(value)
            if maybe_json is not None:
                _collect(maybe_json)
                return
            urls.extend(re.findall(r"https?://[^\s\"'<>]+", value))

    _collect(output)
    return _dedupe_preserve_order(urls)


def is_url_in_domain(url: str, domain: str) -> bool:
    parsed = urlparse(canonicalize_url(url))
    host = parsed.netloc.lower()
    target = domain.lower()
    return host == target or host.endswith(f".{target}")


def _try_parse_json(value: str) -> Any | None:
    value = value.strip()
    if not value:
        return None
    if not (value.startswith("{") or value.startswith("[")):
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        canonical = canonicalize_url(value)
        if canonical in seen:
            continue
        seen.add(canonical)
        deduped.append(value)
    return deduped
