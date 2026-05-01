from __future__ import annotations

import asyncio
import datetime as dt
import uuid
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from atlas.browser_use.client import BrowserUseClient
from atlas.db.engine import SessionLocal
from atlas.db.models import CrawlJob, Document, Program, Source
from atlas.ingest.concurrency import get_active_crawl_for_domain
from atlas.ingest.discovery import discover_and_create_sources
from atlas.ingest.extraction import extract_url
from atlas.ingest.refresh import refresh_source
from atlas.ops.admission import assess_domain_admission
from atlas.ops.domain_policies import load_domain_policies
from atlas.ops.ledger import append_run_record
from atlas.ops.metrics import build_run_summary
from atlas.ops.planner import load_runnable_domains, plan_sources_for_domain
from atlas.ops.policies import classify_error_code, error_kind_from_code
from atlas.storage.client import SupabaseStorageClient


@dataclass(frozen=True)
class OpsRunOptions:
    domains: list[str] | None
    per_domain_limit: int
    global_limit: int
    timeout_seconds: int | None
    discover_first: bool
    discover_seed_urls: list[str]
    failure_rate_threshold: float
    ledger_path: str
    domain_policy_file: str | None = None
    dry_run: bool = False
    persist_ledger: bool = True


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def run_ops_cycle(options: OpsRunOptions) -> dict[str, Any]:
    started = utcnow()
    run_id = str(uuid.uuid4())
    items: list[dict[str, Any]] = []
    sources_queued = 0
    runnable_domain_names: set[str] = set()

    client: BrowserUseClient | None = None
    storage: SupabaseStorageClient | None = None
    async_runner = asyncio.Runner()

    def get_client() -> BrowserUseClient:
        nonlocal client
        if client is None:
            client = BrowserUseClient(poll_timeout_seconds=options.timeout_seconds)
        return client

    def get_storage() -> SupabaseStorageClient:
        nonlocal storage
        if storage is None:
            storage = SupabaseStorageClient()
        return storage

    try:
        with SessionLocal() as session:
            runnable_domains, selection_issues = load_runnable_domains(session, options.domains)
            runnable_domain_names = {d.domain for d in runnable_domains}
            domain_policies = load_domain_policies(options.domain_policy_file)
            for issue in selection_issues:
                error_code = f"blocked_{issue.reason}"
                items.append(
                    {
                        "item_type": "domain_gate",
                        "domain": issue.domain,
                        "status": "blocked",
                        "error_code": error_code,
                        "error_kind": "blocked",
                        "message": issue.reason,
                    }
                )

            discover_seed_map = _resolve_seed_urls(options.discover_seed_urls, [d.domain for d in runnable_domains])
            remaining_global = max(0, options.global_limit)

            for domain_row in runnable_domains:
                domain = domain_row.domain
                if remaining_global <= 0:
                    break
                domain_policy = domain_policies.get(domain)
                admission = assess_domain_admission(session, domain_row=domain_row, policy=domain_policy)
                if not admission.admitted:
                    snapshot = admission.snapshot
                    items.append(
                        {
                            "item_type": "domain_gate",
                            "domain": domain,
                            "status": "blocked",
                            "error_code": f"blocked_{admission.reason}",
                            "error_kind": "blocked",
                            "quality_snapshot": {
                                "succeeded_sources": snapshot.succeeded_sources if snapshot else None,
                                "recent_crawl_window": snapshot.recent_crawl_window if snapshot else None,
                                "recent_attempted_crawls": snapshot.recent_attempted_crawls if snapshot else None,
                                "recent_failed_crawls": snapshot.recent_failed_crawls if snapshot else None,
                                "recent_failure_rate": snapshot.recent_failure_rate if snapshot else None,
                                "avg_parse_confidence": snapshot.avg_parse_confidence if snapshot else None,
                                "succeeded_with_documents": snapshot.succeeded_with_documents if snapshot else None,
                                "zero_program_succeeded_sources": (
                                    snapshot.zero_program_succeeded_sources if snapshot else None
                                ),
                                "zero_program_rate": snapshot.zero_program_rate if snapshot else None,
                            },
                        }
                    )
                    continue

                active = get_active_crawl_for_domain(session, domain)
                if active is not None:
                    items.append(
                        {
                            "item_type": "domain_gate",
                            "domain": domain,
                            "status": "blocked",
                            "error_code": "blocked_active_crawl",
                            "error_kind": "blocked",
                            "crawl_id": active.id,
                            "crawl_status": active.status,
                        }
                    )
                    continue

                if options.discover_first:
                    seeds = list(discover_seed_map.get(domain, []))
                    if domain_policy:
                        seeds.extend(domain_policy.seed_urls)
                    seeds = _dedupe_preserve_order(seeds)
                    if not seeds:
                        items.append(
                            {
                                "item_type": "discover",
                                "domain": domain,
                                "status": "skipped",
                                "error_code": "no_seed_urls",
                                "error_kind": "terminal",
                            }
                        )
                    elif options.dry_run:
                        items.append(
                            {
                                "item_type": "discover",
                                "domain": domain,
                                "status": "skipped",
                                "error_code": "dry_run",
                                "error_kind": "terminal",
                                "seed_urls": seeds,
                            }
                        )
                    else:
                        try:
                            result = async_runner.run(
                                discover_and_create_sources(
                                    session=session,
                                    client=get_client(),
                                    domain=domain,
                                    seed_urls=seeds,
                                )
                            )
                            items.append(
                                {
                                    "item_type": "discover",
                                    "domain": domain,
                                    "status": "succeeded",
                                    "seed_urls": seeds,
                                    "created": len(result.created_sources),
                                    "skipped": len(result.skipped_urls),
                                    "candidates": len(result.candidate_urls or []),
                                    "crawl_id": result.crawl_job.id if result.crawl_job else None,
                                    "retry_count": result.crawl_job.retry_count if result.crawl_job else 0,
                                    "cost_usd": result.crawl_job.browser_use_cost_usd if result.crawl_job else None,
                                }
                            )
                        except Exception as exc:  # noqa: BLE001
                            error_code = classify_error_code(exc)
                            items.append(
                                {
                                    "item_type": "discover",
                                    "domain": domain,
                                    "status": "failed",
                                    "error_code": error_code,
                                    "error_kind": error_kind_from_code(error_code),
                                    "message": str(exc),
                                }
                            )

                planned = plan_sources_for_domain(
                    session,
                    domain_row=domain_row,
                    per_domain_limit=_resolve_per_domain_limit(options.per_domain_limit, domain_policy),
                    global_remaining=remaining_global,
                )
                sources_queued += len(planned)

                for planned_source in planned:
                    if remaining_global <= 0:
                        break
                    remaining_global -= 1

                    if options.dry_run:
                        items.append(
                            {
                                "item_type": planned_source.mode,
                                "mode": planned_source.mode,
                                "domain": planned_source.domain,
                                "source_id": planned_source.source_id,
                                "canonical_url": planned_source.canonical_url,
                                "status": "skipped",
                                "error_code": "dry_run",
                                "error_kind": "terminal",
                            }
                        )
                        continue

                    source = session.get(Source, planned_source.source_id)
                    if source is None:
                        items.append(
                            {
                                "item_type": planned_source.mode,
                                "mode": planned_source.mode,
                                "domain": planned_source.domain,
                                "source_id": planned_source.source_id,
                                "canonical_url": planned_source.canonical_url,
                                "status": "skipped",
                                "error_code": "source_missing",
                                "error_kind": "terminal",
                            }
                        )
                        continue

                    active = get_active_crawl_for_domain(session, domain)
                    if active is not None:
                        items.append(
                            {
                                "item_type": planned_source.mode,
                                "mode": planned_source.mode,
                                "domain": planned_source.domain,
                                "source_id": planned_source.source_id,
                                "canonical_url": planned_source.canonical_url,
                                "status": "blocked",
                                "error_code": "blocked_active_crawl",
                                "error_kind": "blocked",
                                "crawl_id": active.id,
                                "crawl_status": active.status,
                            }
                        )
                        continue

                    try:
                        if planned_source.mode == "refresh_empty":
                            async_runner.run(
                                refresh_source(
                                    session=session,
                                    client=get_client(),
                                    source_id=source.id,
                                    storage=get_storage(),
                                )
                            )
                            doc_id = source.latest_document_id
                        else:
                            doc = async_runner.run(
                                extract_url(
                                    session=session,
                                    client=get_client(),
                                    url=source.url,
                                    source=source,
                                    storage=get_storage(),
                                )
                            )
                            doc_id = doc.id

                        item = _success_item(
                            session=session,
                            domain=planned_source.domain,
                            source=source,
                            mode=planned_source.mode,
                            doc_id=doc_id,
                        )
                        items.append(item)
                    except Exception as exc:  # noqa: BLE001
                        latest_crawl = _latest_crawl_for_source(session, source.id)
                        error_code = classify_error_code(exc)
                        items.append(
                            {
                                "item_type": planned_source.mode,
                                "mode": planned_source.mode,
                                "domain": planned_source.domain,
                                "source_id": source.id,
                                "canonical_url": source.canonical_url,
                                "status": "failed",
                                "error_code": error_code,
                                "error_kind": error_kind_from_code(error_code),
                                "message": str(exc),
                                "crawl_id": latest_crawl.id if latest_crawl else None,
                                "retry_count": latest_crawl.retry_count if latest_crawl else 0,
                                "cost_usd": latest_crawl.browser_use_cost_usd if latest_crawl else None,
                            }
                        )
    finally:
        if client is not None:
            with suppress(Exception):
                async_runner.run(client.close())
        async_runner.close()

    completed = utcnow()
    policy = {
        "failure_rate_threshold": options.failure_rate_threshold,
        "per_domain_limit": options.per_domain_limit,
        "global_limit": options.global_limit,
        "timeout_seconds": options.timeout_seconds,
        "discover_first": options.discover_first,
        "dry_run": options.dry_run,
    }
    summary = build_run_summary(
        run_id=run_id,
        started_at=started.isoformat(),
        completed_at=completed.isoformat(),
        duration_seconds=max(0.0, (completed - started).total_seconds()),
        policy=policy,
        domains_scanned=len(runnable_domain_names),
        sources_queued=sources_queued,
        items=items,
    )
    if options.persist_ledger:
        append_run_record(options.ledger_path, summary)
    return summary


def _success_item(
    *,
    session,
    domain: str,
    source: Source,
    mode: str,
    doc_id: int | None,
) -> dict[str, Any]:
    document = session.get(Document, doc_id) if doc_id else None
    program_count = 0
    parse_confidence = None
    if document is not None:
        program_count = len(session.execute(select(Program).where(Program.document_id == document.id)).scalars().all())
        parse_confidence = document.parse_confidence

    latest_crawl = _latest_crawl_for_source(session, source.id)
    return {
        "item_type": mode,
        "mode": mode,
        "domain": domain,
        "source_id": source.id,
        "canonical_url": source.canonical_url,
        "status": "succeeded",
        "document_id": document.id if document else None,
        "parse_confidence": parse_confidence,
        "program_count": program_count,
        "crawl_id": latest_crawl.id if latest_crawl else None,
        "retry_count": latest_crawl.retry_count if latest_crawl else 0,
        "cost_usd": latest_crawl.browser_use_cost_usd if latest_crawl else None,
    }


def _latest_crawl_for_source(session, source_id: int) -> CrawlJob | None:
    return session.execute(
        select(CrawlJob)
        .where(CrawlJob.source_id == source_id)
        .order_by(CrawlJob.started_at.desc(), CrawlJob.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def _resolve_seed_urls(seed_inputs: list[str], domains: list[str]) -> dict[str, list[str]]:
    seed_map: dict[str, list[str]] = {domain: [] for domain in domains}
    for entry in seed_inputs:
        value = entry.strip()
        if not value:
            continue
        if "=" in value:
            left, right = value.split("=", 1)
            domain = left.strip().lower()
            seed = right.strip()
            if domain in seed_map and seed:
                seed_map[domain].append(seed)
            continue
        for domain in domains:
            seed_map[domain].append(value)
    return seed_map


def _resolve_per_domain_limit(default_limit: int, domain_policy) -> int:
    if domain_policy is None or domain_policy.per_domain_limit is None:
        return default_limit
    return max(1, domain_policy.per_domain_limit)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped
