"""Typed inference helpers shared by program discovery and Ask Atlas."""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence, TypeVar

from sqlalchemy.orm import Session

from atlas.api.schemas import ProgramSearchItem, SourceSearchItem
from atlas.db.models import Document, Program, Source
from atlas.ml.documents import evidence_document_text, program_document_text
from atlas.ml.reranker import FineTunedCrossEncoder, RerankCandidate, Reranker, rerank_candidates

T = TypeVar("T")


@lru_cache(maxsize=2)
def load_reranker(model_path: str, max_length: int, batch_size: int) -> FineTunedCrossEncoder:
    return FineTunedCrossEncoder(model_path, max_length=max_length, batch_size=batch_size)


def rerank_program_items(
    session: Session,
    query: str,
    items: Sequence[ProgramSearchItem],
    reranker: Reranker,
) -> list[ProgramSearchItem]:
    by_id = {item.id: item for item in items}
    candidates: list[RerankCandidate] = []
    for item in items:
        program = session.get(Program, item.id)
        document = session.get(Document, item.document_id)
        source = session.get(Source, item.source_id) if item.source_id is not None else None
        if program is not None:
            candidates.append(RerankCandidate(item.id, program_document_text(program, document, source), "program"))
    return [by_id[candidate.candidate_id] for candidate in rerank_candidates(reranker, query, candidates)]


def rerank_source_items(
    session: Session,
    query: str,
    items: Sequence[SourceSearchItem],
    reranker: Reranker,
) -> list[SourceSearchItem]:
    by_id = {item.id: item for item in items}
    candidates: list[RerankCandidate] = []
    for item in items:
        source = session.get(Source, item.id)
        if source is None:
            continue
        document = session.get(Document, source.latest_document_id) if source.latest_document_id else None
        candidates.append(RerankCandidate(item.id, evidence_document_text(document, source), "source_evidence"))
    return [by_id[candidate.candidate_id] for candidate in rerank_candidates(reranker, query, candidates)]
