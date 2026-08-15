"""Portable, human-readable review exports for relevance labeling."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db.models import Document, Program, Source
from atlas.ml.dataset import RELEVANCE_SCALE, RelevanceDataset
from atlas.ml.documents import evidence_document_text, program_document_text


def build_labeling_review(session: Session, dataset: RelevanceDataset) -> dict[str, Any]:
    """Snapshot all labelable program and source-evidence text for a draft pool."""
    program_ids = {candidate.program_id for query in dataset.queries for candidate in query.candidates if candidate.program_id is not None}
    source_ids = {candidate.source_id for query in dataset.queries for candidate in query.candidates if candidate.source_id is not None}
    rows = session.execute(
        select(Program, Document, Source)
        .join(Document, Program.document_id == Document.id)
        .join(Source, Document.source_id == Source.id)
    ).all()
    programs = {
        program.id: {
            "program_name": program.name,
            "program_text": program_document_text(program, document, source),
        }
        for program, document, source in rows
        if program.id in program_ids
    }
    sources = {
        source.id: {
            "source_title": source.title,
            "evidence_text": evidence_document_text(document, source),
        }
        for source, document in session.execute(
            select(Source, Document).outerjoin(Document, Source.latest_document_id == Document.id)
        ).all()
        if source.id in source_ids
    }
    return {
        "dataset_version": dataset.version,
        "dataset_status": dataset.status,
        "document_representation": dataset.document_representation,
        "relevance_scale": RELEVANCE_SCALE,
        "instructions": [
            "Assign one relevance grade (0–3) and a short reason in the candidate-pool dataset.",
            "Judge the stated query intent, including every explicit constraint; do not infer missing metadata.",
            "Keep the candidate-pool dataset as draft until every candidate is judged, then set status to frozen.",
        ],
        "candidate_documents": {
            **{f"program:{key}": value for key, value in programs.items()},
            **{f"source:{key}": value for key, value in sources.items()},
        },
        "queries": [
            {
                "query_id": query.query_id,
                "query": query.query,
                "intent": query.intent,
                "candidate_collection": query.candidate_collection,
                "candidates": [
                    {
                        "program_id": candidate.program_id,
                        "source_id": candidate.source_id,
                        "canonical_url": candidate.canonical_url,
                        "candidate_source": candidate.candidate_source,
                        "baseline_rank": candidate.baseline_rank,
                    }
                    for candidate in query.candidates
                ],
            }
            for query in dataset.queries
        ],
    }
