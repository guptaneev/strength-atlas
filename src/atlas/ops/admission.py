from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from atlas.db.models import CrawlJob, Document, Domain, Program, Source
from atlas.ops.domain_policies import DomainPolicy


@dataclass(frozen=True)
class DomainQualitySnapshot:
    domain: str
    succeeded_sources: int
    recent_crawl_window: int
    recent_attempted_crawls: int
    recent_failed_crawls: int
    recent_failure_rate: float | None
    avg_parse_confidence: float | None
    succeeded_with_documents: int
    zero_program_succeeded_sources: int
    zero_program_rate: float | None


@dataclass(frozen=True)
class DomainAdmissionDecision:
    admitted: bool
    reason: str | None
    snapshot: DomainQualitySnapshot | None


def build_domain_quality_report(
    session: Session,
    *,
    domain_policies: dict[str, DomainPolicy] | None = None,
    domains: list[str] | None = None,
) -> dict[str, Any]:
    policies = domain_policies or {}
    requested = {d.strip().lower() for d in (domains or []) if d and d.strip()}
    query = select(Domain).order_by(Domain.domain.asc())
    if requested:
        query = query.where(Domain.domain.in_(requested))
    domain_rows = session.execute(query).scalars().all()

    rows: list[dict[str, Any]] = []
    admitted_count = 0
    blocked_count = 0
    for domain_row in domain_rows:
        policy = policies.get(domain_row.domain)
        snapshot = build_domain_quality_snapshot(
            session,
            domain_id=domain_row.id,
            domain=domain_row.domain,
            recent_window=_resolve_window(policy),
        )
        admitted, reason = _assess_snapshot_against_policy(snapshot, policy)
        if admitted:
            admitted_count += 1
        else:
            blocked_count += 1
        rows.append(
            {
                "domain": domain_row.domain,
                "allowlisted": bool(domain_row.allowlisted),
                "paused": bool(domain_row.paused),
                "policy_present": policy is not None,
                "admission_policy_enabled": bool(policy and _has_admission_thresholds(policy)),
                "admitted": admitted,
                "admission_block_reason": reason,
                "succeeded_sources": snapshot.succeeded_sources,
                "recent_crawl_window": snapshot.recent_crawl_window,
                "recent_attempted_crawls": snapshot.recent_attempted_crawls,
                "recent_failed_crawls": snapshot.recent_failed_crawls,
                "recent_failure_rate": snapshot.recent_failure_rate,
                "avg_parse_confidence": snapshot.avg_parse_confidence,
                "succeeded_with_documents": snapshot.succeeded_with_documents,
                "zero_program_succeeded_sources": snapshot.zero_program_succeeded_sources,
                "zero_program_rate": snapshot.zero_program_rate,
                "thresholds": {
                    "admission_min_succeeded_sources": (
                        policy.admission_min_succeeded_sources if policy else None
                    ),
                    "admission_max_recent_failure_rate": (
                        policy.admission_max_recent_failure_rate if policy else None
                    ),
                    "admission_min_avg_parse_confidence": (
                        policy.admission_min_avg_parse_confidence if policy else None
                    ),
                    "admission_max_zero_program_rate": (
                        policy.admission_max_zero_program_rate if policy else None
                    ),
                    "admission_recent_crawl_window": (
                        policy.admission_recent_crawl_window if policy else None
                    ),
                },
            }
        )

    return {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "totals": {
            "domains_count": len(rows),
            "admitted": admitted_count,
            "blocked": blocked_count,
        },
        "by_domain": rows,
    }


def assess_domain_admission(
    session: Session,
    *,
    domain_row: Domain,
    policy: DomainPolicy | None,
) -> DomainAdmissionDecision:
    if policy is None or not _has_admission_thresholds(policy):
        return DomainAdmissionDecision(admitted=True, reason=None, snapshot=None)

    window = _resolve_window(policy)
    snapshot = build_domain_quality_snapshot(session, domain_id=domain_row.id, domain=domain_row.domain, recent_window=window)
    admitted, reason = _assess_snapshot_against_policy(snapshot, policy)
    return DomainAdmissionDecision(admitted=admitted, reason=reason, snapshot=snapshot)


def build_domain_quality_snapshot(
    session: Session,
    *,
    domain_id: int,
    domain: str,
    recent_window: int,
) -> DomainQualitySnapshot:
    succeeded_sources = int(
        session.execute(
            select(func.count(Source.id)).where(Source.domain_id == domain_id, Source.status == "succeeded")
        ).scalar_one()
        or 0
    )

    confidence_values = (
        session.execute(
            select(Document.parse_confidence)
            .select_from(Source)
            .join(Document, Document.id == Source.latest_document_id)
            .where(
                Source.domain_id == domain_id,
                Source.status == "succeeded",
                Document.parse_confidence.is_not(None),
            )
        )
        .scalars()
        .all()
    )
    confidence_floats = [float(value) for value in confidence_values]
    avg_parse_confidence = (
        sum(confidence_floats) / len(confidence_floats) if confidence_floats else None
    )

    succeeded_with_documents = int(
        session.execute(
            select(func.count(Source.id)).where(
                Source.domain_id == domain_id,
                Source.status == "succeeded",
                Source.latest_document_id.is_not(None),
            )
        ).scalar_one()
        or 0
    )

    no_programs = ~exists(select(Program.id).where(Program.document_id == Source.latest_document_id))
    zero_program_succeeded_sources = int(
        session.execute(
            select(func.count(Source.id)).where(
                Source.domain_id == domain_id,
                Source.status == "succeeded",
                Source.latest_document_id.is_not(None),
                no_programs,
            )
        ).scalar_one()
        or 0
    )
    zero_program_rate = (
        zero_program_succeeded_sources / succeeded_with_documents
        if succeeded_with_documents
        else None
    )

    window = max(1, recent_window)
    recent_rows = (
        session.execute(
            select(CrawlJob.status)
            .select_from(CrawlJob)
            .join(Source, Source.id == CrawlJob.source_id)
            .where(Source.domain_id == domain_id)
            .order_by(CrawlJob.started_at.desc(), CrawlJob.id.desc())
            .limit(window)
        )
        .scalars()
        .all()
    )
    attempted_statuses = [status for status in recent_rows if status in {"succeeded", "failed"}]
    recent_attempted_crawls = len(attempted_statuses)
    recent_failed_crawls = len([status for status in attempted_statuses if status == "failed"])
    recent_failure_rate = (
        recent_failed_crawls / recent_attempted_crawls if recent_attempted_crawls else None
    )

    return DomainQualitySnapshot(
        domain=domain,
        succeeded_sources=succeeded_sources,
        recent_crawl_window=window,
        recent_attempted_crawls=recent_attempted_crawls,
        recent_failed_crawls=recent_failed_crawls,
        recent_failure_rate=recent_failure_rate,
        avg_parse_confidence=avg_parse_confidence,
        succeeded_with_documents=succeeded_with_documents,
        zero_program_succeeded_sources=zero_program_succeeded_sources,
        zero_program_rate=zero_program_rate,
    )


def _resolve_window(policy: DomainPolicy | None) -> int:
    if policy is None or policy.admission_recent_crawl_window is None:
        return 20
    return max(1, policy.admission_recent_crawl_window)


def _has_admission_thresholds(policy: DomainPolicy) -> bool:
    return any(
        value is not None
        for value in (
            policy.admission_min_succeeded_sources,
            policy.admission_max_recent_failure_rate,
            policy.admission_min_avg_parse_confidence,
            policy.admission_max_zero_program_rate,
        )
    )


def _assess_snapshot_against_policy(
    snapshot: DomainQualitySnapshot,
    policy: DomainPolicy | None,
) -> tuple[bool, str | None]:
    if policy is None or not _has_admission_thresholds(policy):
        return True, None

    if (
        policy.admission_min_succeeded_sources is not None
        and snapshot.succeeded_sources < policy.admission_min_succeeded_sources
    ):
        return False, "domain_quality_insufficient_succeeded_sources"

    if policy.admission_max_recent_failure_rate is not None:
        failure_rate = snapshot.recent_failure_rate
        if failure_rate is None:
            return False, "domain_quality_insufficient_recent_crawl_history"
        if failure_rate > policy.admission_max_recent_failure_rate:
            return False, "domain_quality_recent_failure_rate_exceeded"

    if policy.admission_min_avg_parse_confidence is not None:
        if snapshot.avg_parse_confidence is None:
            return False, "domain_quality_missing_parse_confidence"
        if snapshot.avg_parse_confidence < policy.admission_min_avg_parse_confidence:
            return False, "domain_quality_low_parse_confidence"

    if policy.admission_max_zero_program_rate is not None:
        zero_program_rate = snapshot.zero_program_rate
        if zero_program_rate is None:
            return False, "domain_quality_missing_zero_program_rate"
        if zero_program_rate > policy.admission_max_zero_program_rate:
            return False, "domain_quality_high_zero_program_rate"

    return True, None
