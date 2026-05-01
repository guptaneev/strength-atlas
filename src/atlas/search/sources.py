from __future__ import annotations

from typing import Iterable

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from atlas.db.models import Document, Domain, Source


def search_sources(
    session: Session,
    query: str,
    domain: str | None = None,
    limit: int = 25,
) -> Iterable[Source]:
    stmt = build_source_search_statement(query=query, domain=domain, limit=limit)
    return session.execute(stmt).scalars().all()


def build_source_search_statement(query: str, domain: str | None = None, limit: int = 25):
    ts_query = func.plainto_tsquery("english", query) if query else None

    ranked_documents = select(
        Document.source_id.label("source_id"),
        func.max(
            func.ts_rank(Document.content_tsv, ts_query) if ts_query is not None else 0.0
        ).label("text_rank"),
        func.max(Document.created_at).label("latest_document_at"),
    ).group_by(Document.source_id)

    if ts_query is not None:
        ranked_documents = ranked_documents.where(Document.content_tsv.op("@@")(ts_query))

    ranked_documents_subq = ranked_documents.subquery()

    stmt = (
        select(Source)
        .join(ranked_documents_subq, ranked_documents_subq.c.source_id == Source.id)
        .join(Domain, Domain.id == Source.domain_id)
    )
    if domain is not None:
        stmt = stmt.where(Domain.domain == domain)
    page_quality_score = case((Source.canonical_url.ilike("%/category/%"), -1), else_=0)
    # Keep SQLAlchemy expression simple and portable across tests.
    for pattern in ("%/tag/%", "%/author/%", "%/blog/best-%", "%/product-category/%"):
        page_quality_score = page_quality_score + case((Source.canonical_url.ilike(pattern), -1), else_=0)
    for pattern in ("%/program%", "%/template%", "%/how-to-%", "%/shop/%"):
        page_quality_score = page_quality_score + case((Source.canonical_url.ilike(pattern), 1), else_=0)

    stmt = stmt.order_by(
        ranked_documents_subq.c.text_rank.desc(),
        page_quality_score.desc(),
        ranked_documents_subq.c.latest_document_at.desc().nullslast(),
        Source.id.asc(),
    ).limit(limit)
    return stmt
