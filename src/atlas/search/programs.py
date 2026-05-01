from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import case, func, literal, select
from sqlalchemy.orm import Session

from atlas.db.models import CrawlJob, Document, Domain, Program, Source


@dataclass(frozen=True)
class ProgramSearchFilters:
    days_per_week: int | None = None
    specialization: str | None = None
    experience_level: str | None = None
    progression_type: str | None = None
    split_type: str | None = None
    domain: str | None = None


def search_programs(
    session: Session, query: str | None, filters: ProgramSearchFilters, limit: int = 25
) -> Iterable[Program]:
    stmt = build_program_search_statement(query=query, filters=filters, limit=limit)
    rows = session.execute(stmt).all()
    return [row[0] for row in rows]


def build_program_search_statement(query: str | None, filters: ProgramSearchFilters, limit: int = 25):
    structured_score = literal(0)
    stmt = (
        select(
            Program,
            structured_score.label("structured_score"),
        )
        .join(Program.document)
        .join(Source, Source.id == Document.source_id)
        .join(Domain, Domain.id == Source.domain_id)
        .outerjoin(CrawlJob, CrawlJob.id == Document.crawl_job_id)
    )
    if filters.days_per_week is not None:
        stmt = stmt.where(Program.days_per_week == filters.days_per_week)
        structured_score = structured_score + case((Program.days_per_week == filters.days_per_week, 1), else_=0)
    if filters.specialization:
        stmt = stmt.where(Program.specialization == filters.specialization)
        structured_score = structured_score + case((Program.specialization == filters.specialization, 1), else_=0)
    if filters.experience_level:
        stmt = stmt.where(Program.experience_level == filters.experience_level)
        structured_score = structured_score + case(
            (Program.experience_level == filters.experience_level, 1), else_=0
        )
    if filters.progression_type:
        stmt = stmt.where(Program.progression_type == filters.progression_type)
        structured_score = structured_score + case(
            (Program.progression_type == filters.progression_type, 1), else_=0
        )
    if filters.split_type:
        stmt = stmt.where(Program.split_type == filters.split_type)
        structured_score = structured_score + case((Program.split_type == filters.split_type, 1), else_=0)
    if filters.domain is not None:
        stmt = stmt.where(Domain.domain == filters.domain)
        structured_score = structured_score + case((Domain.domain == filters.domain, 1), else_=0)

    text_rank = literal(0.0)
    if query:
        ts_query = func.plainto_tsquery("english", query)
        stmt = stmt.where(Document.content_tsv.op("@@")(ts_query))
        text_rank = func.ts_rank(Document.content_tsv, ts_query)

    # Downweight aggregate/listing URLs that often match broad terms but are
    # less useful than program/detail pages for intent-focused program search.
    page_quality_score = literal(0)
    for pattern in ("%/category/%", "%/tag/%", "%/author/%", "%/blog/best-%", "%/product-category/%"):
        page_quality_score = page_quality_score + case((Source.canonical_url.ilike(pattern), -1), else_=0)
    for pattern in ("%/program%", "%/template%", "%/how-to-%", "%/shop/%"):
        page_quality_score = page_quality_score + case((Source.canonical_url.ilike(pattern), 1), else_=0)

    newest_crawl = func.coalesce(CrawlJob.started_at, Document.created_at, Program.created_at)
    stmt = stmt.with_only_columns(
        Program,
        structured_score.label("structured_score"),
        text_rank.label("text_rank"),
        page_quality_score.label("page_quality_score"),
        newest_crawl.label("newest_crawl"),
    )
    stmt = stmt.order_by(
        structured_score.desc(),
        text_rank.desc(),
        page_quality_score.desc(),
        Program.confidence.desc().nullslast(),
        newest_crawl.desc().nullslast(),
    )
    stmt = stmt.limit(limit)
    return stmt
