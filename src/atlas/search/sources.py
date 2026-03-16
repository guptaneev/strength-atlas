from __future__ import annotations

from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.db.models import Document, Source


def search_sources(
    session: Session,
    query: str,
    domain_id: int | None = None,
    limit: int = 25,
) -> Iterable[Source]:
    stmt = select(Source).join(Document, Document.source_id == Source.id)
    if domain_id is not None:
        stmt = stmt.where(Source.domain_id == domain_id)
    if query:
        stmt = stmt.where(Document.content_tsv.op("@@")(func.plainto_tsquery("english", query)))
    stmt = stmt.order_by(Source.last_crawled_at.desc().nullslast()).limit(limit)
    return session.execute(stmt).scalars().all()
