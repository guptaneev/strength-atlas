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
from atlas.config.settings import get_settings
from atlas.db.models import CrawlJob, Domain, Source
from atlas.ingest.retries import is_retryable_browser_use_error
from atlas.ingest.url_policy import apply_discovery_url_policy, build_discovery_url_policy


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
    domain_row = session.execute(select(Domain).where(Domain.domain == domain)).scalar_one_or_none()
    if domain_row is None:
        return DiscoveryResult(created_sources=created, skipped_urls=list(candidate_urls))

    for url in candidate_urls:
        canonical = safe_canonicalize_url(url)
        if canonical is None:
            skipped.append(url)
            continue
        if not is_url_in_domain(canonical, domain):
            skipped.append(canonical)
            continue
        if is_duplicate_canonical(session, canonical):
            skipped.append(canonical)
            continue
        source = Source(
            url=canonical,
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
        settings = get_settings()
        max_retries = max(0, settings.max_crawl_retries)
        total_attempts = max_retries + 1
        result = None
        for attempt_index in range(total_attempts):
            try:
                result = await client.discover_urls(domain=domain, seed_urls=seed_urls)
                break
            except Exception as exc:
                if attempt_index < max_retries and is_retryable_browser_use_error(exc):
                    crawl_job.retry_count = attempt_index + 1
                    crawl_job.error_message = (
                        f"discover attempt {attempt_index + 1}/{total_attempts} failed: {exc}; retrying"
                    )
                    crawl_job.status = "running"
                    session.commit()
                    continue
                crawl_job.retry_count = min(attempt_index, max_retries)
                raise
        if result is None:
            raise RuntimeError("discover produced no result")

        crawl_job.browser_use_session_id = result.session_id
        crawl_job.browser_use_live_url = result.live_url
        crawl_job.browser_use_cost_usd = result.total_cost_usd

        discovered = parse_candidate_urls(result.output)
        discovered = [u for u in discovered if is_url_in_domain(u, domain)]
        policy = build_discovery_url_policy(
            blocked_path_tokens_csv=getattr(settings, "discovery_blocked_path_tokens", ""),
            max_candidates=getattr(settings, "discovery_max_candidates_per_run", 200),
        )
        filtered = apply_discovery_url_policy(discovered, policy)
        created = create_sources_from_urls(session, domain, filtered.accepted_urls)

        crawl_job.status = "succeeded"
        crawl_job.error_message = None
        crawl_job.completed_at = dt.datetime.now(dt.UTC)
        session.commit()
        return DiscoveryResult(
            created_sources=created.created_sources,
            skipped_urls=created.skipped_urls + filtered.rejected_urls,
            crawl_job=crawl_job,
            candidate_urls=filtered.accepted_urls,
        )
    except Exception as exc:
        if hasattr(session, "rollback"):
            session.rollback()
        crawl_job.status = "failed"
        settings = get_settings()
        total_attempts = max(0, settings.max_crawl_retries) + 1
        retry_count = int(crawl_job.retry_count or 0)
        crawl_job.error_message = f"discover failed after {retry_count + 1}/{total_attempts} attempts: {exc}"
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
    cleaned = [safe_canonicalize_url(u) for u in urls]
    return _dedupe_preserve_order([u for u in cleaned if u])


def is_url_in_domain(url: str, domain: str) -> bool:
    canonical = safe_canonicalize_url(url)
    if canonical is None:
        return False
    parsed = urlparse(canonical)
    host = parsed.netloc.lower()
    if not host:
        return False
    target = domain.lower()
    return host == target or host.endswith(f".{target}")


def safe_canonicalize_url(url: str) -> str | None:
    raw = url.strip()
    raw_parsed = urlparse(raw)
    if raw_parsed.scheme and raw_parsed.scheme.lower() not in ("http", "https"):
        return None
    try:
        canonical = canonicalize_url(raw)
    except Exception:
        return None
    parsed = urlparse(canonical)
    if not parsed.netloc:
        return None
    if " " in parsed.netloc:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    return canonical


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
