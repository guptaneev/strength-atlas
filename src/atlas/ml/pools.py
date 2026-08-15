"""Candidate-pool creation from baseline results plus reproducible negatives."""

from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db.models import Document, Program, Source
from atlas.ml.dataset import CandidateJudgment, RelevanceDataset, RelevanceQuery
from atlas.search.programs import ProgramSearchFilters, search_programs


def build_candidate_pools(
    session: Session,
    dataset: RelevanceDataset,
    *,
    retrieval_depth: int = 50,
    random_negatives: int = 10,
    seed: int = 42,
) -> RelevanceDataset:
    """Attach baseline candidates and random negatives to otherwise query-only data."""
    rng = random.Random(seed)
    all_programs = list(session.scalars(select(Program).order_by(Program.id)))
    queries: list[RelevanceQuery] = []
    for query in dataset.queries:
        candidates = list(query.candidates)
        known_ids = {candidate.program_id for candidate in candidates if candidate.program_id is not None}
        for rank, program in enumerate(
            search_programs(session, query.query, ProgramSearchFilters(), limit=retrieval_depth), start=1
        ):
            if program.id in known_ids:
                continue
            source = _source_for_program(session, program)
            # These lexically/structurally close retrieval results are the
            # initial hard-negative mining source. Human labels decide whether
            # any individual item is actually negative.
            candidates.append(CandidateJudgment(program.id, source.canonical_url if source else None, "retriever_hard_candidate", rank, None, None, None))
            known_ids.add(program.id)
        eligible = [program for program in all_programs if program.id not in known_ids]
        for program in rng.sample(eligible, k=min(random_negatives, len(eligible))):
            source = _source_for_program(session, program)
            candidates.append(CandidateJudgment(program.id, source.canonical_url if source else None, "random_negative", None, None, None, None))
        queries.append(RelevanceQuery(query.query_id, query.query, query.intent, candidates))
    return RelevanceDataset(dataset.version, "draft", dataset.document_representation, queries)


def _source_for_program(session: Session, program: Program) -> Source | None:
    document = session.get(Document, program.document_id)
    return session.get(Source, document.source_id) if document else None
