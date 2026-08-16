from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import case, func, literal, select
from sqlalchemy.orm import Session

from atlas.db.models import CrawlJob, Document, Domain, Program, Source
from atlas.search.query_expansion import QueryIntent, expand_query


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
    exact = [row[0] for row in rows]
    if not query or len(exact) >= limit:
        return exact

    # Exact all-term retrieval keeps precision high. Candidate expansion fills
    # only the shortfall, preserving exact results ahead of broader candidates.
    fallback_stmt = build_program_candidate_fallback_statement(
        query=query,
        filters=filters,
        limit=max(limit * 2, 25),
    )
    seen = {program.id for program in exact}
    expanded = [row[0] for row in session.execute(fallback_stmt).all() if row[0].id not in seen]
    return (exact + expanded)[:limit]


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


def build_program_candidate_fallback_statement(
    query: str,
    filters: ProgramSearchFilters,
    limit: int = 50,
):
    """Return high-recall candidates using expanded terms and soft intent boosts.

    This is the lexical/intent candidate leg of future hybrid retrieval. A
    vector retriever can later union into this same candidate stage before the
    cross-encoder reranks it.
    """
    intent = expand_query(query)
    ts_query = _expanded_ts_query(intent)
    text_rank = func.ts_rank(Document.content_tsv, ts_query)
    intent_score = _intent_score(intent)
    stmt = (
        select(Program, text_rank.label("text_rank"), intent_score.label("intent_score"))
        .join(Program.document)
        .join(Source, Source.id == Document.source_id)
        .join(Domain, Domain.id == Source.domain_id)
        .where(Document.content_tsv.op("@@")(ts_query))
    )
    stmt = _apply_hard_filters(stmt, filters)
    return stmt.order_by(
        intent_score.desc(),
        text_rank.desc(),
        Program.confidence.desc().nullslast(),
        Program.id.asc(),
    ).limit(limit)


def _expanded_ts_query(intent: QueryIntent):
    # plainto_tsquery prevents query-string syntax from becoming executable SQL;
    # OR-ing the individual safe terms gives candidate recall without pretending
    # that every natural-language word is a required program attribute.
    terms = [func.plainto_tsquery("english", term) for term in intent.terms]
    if not terms:
        return func.plainto_tsquery("english", "program")
    ts_query = terms[0]
    for term in terms[1:]:
        ts_query = ts_query.op("||")(term)
    return ts_query


def _intent_score(intent: QueryIntent):
    score = literal(0)
    if intent.days_per_week is not None:
        score = score + case((Program.days_per_week == intent.days_per_week, 3), else_=0)
    if intent.experience_level is not None:
        score = score + case((Program.experience_level == intent.experience_level, 3), else_=0)
    if intent.split_type is not None:
        score = score + case((Program.split_type == intent.split_type, 2), else_=0)
    return score


def _apply_hard_filters(stmt, filters: ProgramSearchFilters):
    if filters.days_per_week is not None:
        stmt = stmt.where(Program.days_per_week == filters.days_per_week)
    if filters.specialization:
        stmt = stmt.where(Program.specialization == filters.specialization)
    if filters.experience_level:
        stmt = stmt.where(Program.experience_level == filters.experience_level)
    if filters.progression_type:
        stmt = stmt.where(Program.progression_type == filters.progression_type)
    if filters.split_type:
        stmt = stmt.where(Program.split_type == filters.split_type)
    if filters.domain is not None:
        stmt = stmt.where(Domain.domain == filters.domain)
    return stmt
