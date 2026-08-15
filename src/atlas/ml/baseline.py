"""Frozen baseline evaluation with inspectable per-query rankings."""

from __future__ import annotations

from statistics import fmean
from typing import Any

from sqlalchemy.orm import Session

from atlas.db.models import Document, Program, Source
from atlas.ml.dataset import RelevanceDataset
from atlas.search.metrics import evaluate_ranking
from atlas.search.programs import ProgramSearchFilters, search_programs


def evaluate_baseline(session: Session, dataset: RelevanceDataset, *, k: int = 10, retrieval_depth: int = 50) -> dict[str, Any]:
    """Evaluate the current program retriever only after all pool labels are complete."""
    dataset.validate(require_complete_judgments=True)
    per_query: list[dict[str, Any]] = []
    for query in dataset.queries:
        labels = {candidate.program_id: candidate for candidate in query.candidates if candidate.program_id is not None}
        ranked = search_programs(session, query.query, ProgramSearchFilters(), limit=retrieval_depth)
        observed = [program for program in ranked if program.id in labels]
        relevance = [labels[program.id].relevance or 0 for program in observed]
        total_relevant = sum((candidate.relevance or 0) > 0 for candidate in query.candidates)
        metrics = evaluate_ranking(relevance, total_relevant=total_relevant, k=k)
        rows = []
        for rank, program in enumerate(observed, start=1):
            document = session.get(Document, program.document_id)
            source = session.get(Source, document.source_id) if document else None
            judgment = labels[program.id]
            rows.append({
                "rank": rank, "program_id": program.id, "program_name": program.name,
                "canonical_url": source.canonical_url if source else judgment.canonical_url,
                "baseline_score": judgment.baseline_score, "relevance": judgment.relevance,
            })
        per_query.append({
            "query_id": query.query_id, "query": query.query, "metrics": metrics.__dict__, "ranking": rows,
        })
    metric_names = ("ndcg", "reciprocal_rank", "recall", "precision")
    averages = {name: fmean(row["metrics"][name] for row in per_query) if per_query else 0.0 for name in metric_names}
    return {
        "experiment": "program_search_baseline", "dataset_version": dataset.version,
        "dataset_status": dataset.status, "k": k, "retrieval_depth": retrieval_depth,
        "metrics": {"ndcg_at_k": averages["ndcg"], "mrr": averages["reciprocal_rank"], "recall_at_k": averages["recall"], "precision_at_k": averages["precision"]},
        "queries": per_query,
    }
