"""Candidate-pool creation from baseline results plus reproducible negatives."""

from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db.models import Document, Program, Source
from atlas.ml.dataset import CandidateJudgment, RelevanceDataset, RelevanceQuery
from atlas.search.programs import ProgramSearchFilters, search_programs
from atlas.search.sources import search_sources


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
    all_sources = list(session.scalars(select(Source).order_by(Source.id)))
    # Candidate pools can contain hundreds of programs. Fetch their source URLs
    # once rather than issuing a document/source lookup for every candidate.
    source_urls = dict(
        session.execute(
            select(Program.id, Source.canonical_url)
            .join(Document, Program.document_id == Document.id)
            .join(Source, Document.source_id == Source.id)
        ).all()
    )
    queries: list[RelevanceQuery] = []
    for query in dataset.queries:
        if query.candidate_collection == "source_evidence":
            queries.append(_build_source_pool(query, all_sources, session, rng, retrieval_depth, random_negatives))
            continue
        candidates = list(query.candidates)
        known_ids = {candidate.program_id for candidate in candidates if candidate.program_id is not None}
        for rank, program in enumerate(
            search_programs(session, query.query, ProgramSearchFilters(), limit=retrieval_depth), start=1
        ):
            if program.id in known_ids:
                continue
            # These lexically/structurally close retrieval results are the
            # initial hard-negative mining source. Human labels decide whether
            # any individual item is actually negative.
            candidates.append(CandidateJudgment(program.id, source_urls.get(program.id), "retriever_hard_candidate", rank, None, None, None))
            known_ids.add(program.id)
        eligible = [program for program in all_programs if program.id not in known_ids]
        for program in rng.sample(eligible, k=min(random_negatives, len(eligible))):
            candidates.append(CandidateJudgment(program.id, source_urls.get(program.id), "random_negative", None, None, None, None))
        queries.append(RelevanceQuery(query.query_id, query.query, query.intent, candidates, query.candidate_collection))
    return RelevanceDataset(dataset.version, "draft", dataset.document_representation, queries)


def _build_source_pool(
    query: RelevanceQuery,
    all_sources: list[Source],
    session: Session,
    rng: random.Random,
    retrieval_depth: int,
    random_negatives: int,
) -> RelevanceQuery:
    candidates = list(query.candidates)
    known_ids = {candidate.source_id for candidate in candidates if candidate.source_id is not None}
    for rank, source in enumerate(search_sources(session, query.query, limit=retrieval_depth), start=1):
        if source.id in known_ids:
            continue
        candidates.append(CandidateJudgment(None, source.canonical_url, "retriever_hard_candidate", rank, None, None, None, source.id))
        known_ids.add(source.id)
    eligible = [source for source in all_sources if source.id not in known_ids and source.latest_document_id is not None]
    for source in rng.sample(eligible, k=min(random_negatives, len(eligible))):
        candidates.append(CandidateJudgment(None, source.canonical_url, "random_negative", None, None, None, None, source.id))
    return RelevanceQuery(query.query_id, query.query, query.intent, candidates, query.candidate_collection)
