"""Frozen baseline evaluation with inspectable per-query rankings."""

from __future__ import annotations

from statistics import fmean
from typing import Any

from sqlalchemy.orm import Session

from atlas.db.models import Document, Program, Source
from atlas.ml.dataset import RelevanceDataset
from atlas.search.metrics import evaluate_ranking
from atlas.search.programs import ProgramSearchFilters, search_programs
from atlas.search.sources import search_sources


def evaluate_baseline(session: Session, dataset: RelevanceDataset, *, k: int = 10, retrieval_depth: int = 50) -> dict[str, Any]:
    """Evaluate the matching retrieval collection after all pool labels are complete."""
    dataset.validate(require_complete_judgments=True)
    per_query: list[dict[str, Any]] = []
    for query in dataset.queries:
        if query.candidate_collection == "source_evidence":
            labels = {candidate.source_id: candidate for candidate in query.candidates if candidate.source_id is not None}
            ranked = search_sources(session, query.query, limit=retrieval_depth)
            observed = [source for source in ranked if source.id in labels]
            relevance = [labels[source.id].relevance or 0 for source in observed]
        else:
            labels = {candidate.program_id: candidate for candidate in query.candidates if candidate.program_id is not None}
            ranked = search_programs(session, query.query, ProgramSearchFilters(), limit=retrieval_depth)
            observed = [program for program in ranked if program.id in labels]
            relevance = [labels[program.id].relevance or 0 for program in observed]
        total_relevant = sum((candidate.relevance or 0) > 0 for candidate in query.candidates)
        metrics = evaluate_ranking(relevance, total_relevant=total_relevant, k=k)
        rows = []
        for rank, candidate in enumerate(observed, start=1):
            if query.candidate_collection == "source_evidence":
                judgment = labels[candidate.id]
                rows.append({"rank": rank, "source_id": candidate.id, "canonical_url": candidate.canonical_url,
                             "baseline_score": judgment.baseline_score, "relevance": judgment.relevance})
            else:
                document = session.get(Document, candidate.document_id)
                source = session.get(Source, document.source_id) if document else None
                judgment = labels[candidate.id]
                rows.append({"rank": rank, "program_id": candidate.id, "program_name": candidate.name,
                             "canonical_url": source.canonical_url if source else judgment.canonical_url,
                             "baseline_score": judgment.baseline_score, "relevance": judgment.relevance})
        per_query.append({
            "query_id": query.query_id, "query": query.query, "metrics": metrics.__dict__, "ranking": rows,
        })
    metric_names = ("ndcg", "reciprocal_rank", "recall", "precision")
    averages = {name: fmean(row["metrics"][name] for row in per_query) if per_query else 0.0 for name in metric_names}
    return {
        "experiment": _experiment_name(dataset), "dataset_version": dataset.version,
        "dataset_status": dataset.status, "k": k, "retrieval_depth": retrieval_depth,
        "metrics": {"ndcg_at_k": averages["ndcg"], "mrr": averages["reciprocal_rank"], "recall_at_k": averages["recall"], "precision_at_k": averages["precision"]},
        "queries": per_query,
    }


def _experiment_name(dataset: RelevanceDataset) -> str:
    collections = {query.candidate_collection for query in dataset.queries}
    if collections == {"source_evidence"}:
        return "source_search_baseline"
    if collections == {"program"}:
        return "program_search_baseline"
    raise ValueError("A baseline dataset must contain exactly one candidate collection")
