from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from atlas.db.models import Domain, Program, Source


@dataclass(frozen=True)
class DomainSelectionIssue:
    domain: str
    reason: str


@dataclass(frozen=True)
class PlannedSource:
    source_id: int
    domain: str
    canonical_url: str
    mode: str


def load_runnable_domains(
    session: Session,
    requested_domains: list[str] | None,
) -> tuple[list[Domain], list[DomainSelectionIssue]]:
    if requested_domains:
        requested = [d.strip().lower() for d in requested_domains if d.strip()]
        rows = session.execute(select(Domain).where(Domain.domain.in_(requested))).scalars().all()
        by_domain = {row.domain: row for row in rows}

        runnable: list[Domain] = []
        issues: list[DomainSelectionIssue] = []
        for domain in requested:
            row = by_domain.get(domain)
            if row is None:
                issues.append(DomainSelectionIssue(domain=domain, reason="domain_not_found"))
                continue
            if not row.allowlisted:
                issues.append(DomainSelectionIssue(domain=domain, reason="domain_not_allowlisted"))
                continue
            if row.paused:
                issues.append(DomainSelectionIssue(domain=domain, reason="domain_paused"))
                continue
            runnable.append(row)
        return runnable, issues

    rows = session.execute(
        select(Domain)
        .where(Domain.allowlisted.is_(True), Domain.paused.is_(False))
        .order_by(Domain.domain.asc())
    ).scalars().all()
    return rows, []


def plan_sources_for_domain(
    session: Session,
    *,
    domain_row: Domain,
    per_domain_limit: int,
    global_remaining: int,
) -> list[PlannedSource]:
    cap = max(0, min(per_domain_limit, global_remaining))
    if cap == 0:
        return []

    pending = session.execute(
        select(Source)
        .where(
            Source.domain_id == domain_row.id,
            Source.status == "pending",
        )
        .order_by(Source.id.asc())
        .limit(cap)
    ).scalars().all()

    planned_pending = [
        PlannedSource(
            source_id=src.id,
            domain=domain_row.domain,
            canonical_url=src.canonical_url,
            mode="extract_pending",
        )
        for src in pending
    ]

    remaining = cap - len(planned_pending)
    if remaining <= 0:
        return planned_pending

    no_programs = ~exists(select(Program.id).where(Program.document_id == Source.latest_document_id))
    empty_sources = session.execute(
        select(Source)
        .where(
            Source.domain_id == domain_row.id,
            Source.status == "succeeded",
            Source.latest_document_id.is_not(None),
            no_programs,
        )
        .order_by(Source.id.asc())
        .limit(remaining)
    ).scalars().all()

    planned_empty = [
        PlannedSource(
            source_id=src.id,
            domain=domain_row.domain,
            canonical_url=src.canonical_url,
            mode="refresh_empty",
        )
        for src in empty_sources
    ]
    return planned_pending + planned_empty
