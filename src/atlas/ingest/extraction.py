from __future__ import annotations

import datetime as dt

from sqlalchemy import func
from sqlalchemy.orm import Session

from atlas.browser_use.client import BrowserUseClient
from atlas.db.models import Claim, CrawlJob, Document, Program, Source
from atlas.ingest.normalization import build_content_tsv_text, normalize_extraction
from atlas.storage.paths import extracted_json_path, html_path


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


async def extract_url(
    session: Session,
    client: BrowserUseClient,
    url: str,
    source: Source | None = None,
) -> Document:
    crawl_job = CrawlJob(
        job_type="extract",
        source_id=source.id if source else None,
        target_url=url,
        status="pending",
        started_at=utcnow(),
    )
    session.add(crawl_job)
    session.commit()

    crawl_job.status = "running"
    session.commit()

    try:
        result = await client.extract_url(url)
        crawl_job.browser_use_session_id = result.session_id
        crawl_job.browser_use_live_url = result.live_url
        crawl_job.browser_use_cost_usd = result.total_cost_usd
        crawl_job.status = "succeeded"
        crawl_job.completed_at = utcnow()
    except Exception as exc:
        crawl_job.status = "failed"
        crawl_job.error_message = str(exc)
        crawl_job.completed_at = utcnow()
        session.commit()
        raise

    normalized = normalize_extraction(result.output)
    if source:
        source.title = normalized.title
        source.author = normalized.author
        source.source_type = normalized.source_type

    document = Document(
        source_id=source.id if source else 0,
        crawl_job_id=crawl_job.id,
        raw_text=normalized.raw_text,
        html_storage_path=html_path(source.id if source else 0, crawl_job.id),
        extracted_json_storage_path=extracted_json_path(source.id if source else 0, crawl_job.id),
        parse_confidence=0.5,
        created_at=utcnow(),
    )
    content_text = build_content_tsv_text(normalized.title, normalized.summary, normalized.raw_text)
    document.content_tsv = func.to_tsvector("english", content_text)
    session.add(document)
    session.flush()

    for program in normalized.programs:
        session.add(
            Program(
                document_id=document.id,
                name=program.get("name"),
                coach_name=program.get("coach_name"),
                days_per_week=program.get("days_per_week"),
                specialization=program.get("specialization"),
                experience_level=program.get("experience_level"),
                progression_type=program.get("progression_type"),
                split_type=program.get("split_type"),
                summary=program.get("summary"),
                confidence=program.get("confidence"),
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )

    for claim in normalized.claims:
        session.add(
            Claim(
                document_id=document.id,
                program_id=claim.get("program_id"),
                claim_type=claim.get("claim_type"),
                raw_text=claim.get("raw_text"),
                normalized_value=claim.get("normalized_value"),
                confidence=claim.get("confidence"),
                created_at=utcnow(),
            )
        )

    if source:
        source.latest_document_id = document.id
        source.last_crawled_at = utcnow()
        source.status = "succeeded"

    session.commit()
    return document
