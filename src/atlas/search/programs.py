from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db.models import Document, Domain, Program, Source


@dataclass(frozen=True)
class ProgramSearchFilters:
    days_per_week: int | None = None
    specialization: str | None = None
    experience_level: str | None = None
    progression_type: str | None = None
    split_type: str | None = None
    domain: str | None = None


def search_programs(
    session: Session,
    query: str | None,
    filters: ProgramSearchFilters,
    limit: int = 25,
) -> Iterable[Program]:
    stmt = (
        select(Program)
        .join(Program.document)
        .join(Source, Source.id == Document.source_id)
        .join(Domain, Domain.id == Source.domain_id)
    )
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
    if query:
        stmt = stmt.where(Program.summary.ilike(f"%{query}%"))
    stmt = stmt.order_by(Program.confidence.desc().nullslast(), Program.created_at.desc())
    stmt = stmt.limit(limit)
    return session.execute(stmt).scalars().all()
