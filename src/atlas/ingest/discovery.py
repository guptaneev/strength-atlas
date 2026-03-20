from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db.models import Domain, Source


@dataclass(frozen=True)
class DiscoveryResult:
    created_sources: list[Source]
    skipped_urls: list[str]


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
