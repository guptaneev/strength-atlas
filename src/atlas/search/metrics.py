"""Ranking metrics for retrieval evaluation.

Each function accepts relevance grades in ranked order. A relevance grade of
zero means irrelevant; any positive grade means relevant.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class RankingMetrics:
    """Metrics for one ranked result list and one query."""

    precision: float
    recall: float
    reciprocal_rank: float
    ndcg: float


def _validate_k(k: int) -> None:
    if k < 1:
        raise ValueError("k must be at least 1")


def precision_at_k(relevance: Sequence[float], k: int) -> float:
    """Return the fraction of the first k results that are relevant."""
    _validate_k(k)
    return sum(score > 0 for score in relevance[:k]) / k


def recall_at_k(relevance: Sequence[float], total_relevant: int, k: int) -> float:
    """Return the fraction of all relevant items retrieved in the first k."""
    _validate_k(k)
    if total_relevant < 0:
        raise ValueError("total_relevant cannot be negative")
    if total_relevant == 0:
        return 0.0
    retrieved_relevant = sum(score > 0 for score in relevance[:k])
    return retrieved_relevant / total_relevant


def reciprocal_rank(relevance: Sequence[float], k: int | None = None) -> float:
    """Return the reciprocal rank of the first relevant result."""
    if k is not None:
        _validate_k(k)
        relevance = relevance[:k]
    for rank, score in enumerate(relevance, start=1):
        if score > 0:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(relevance: Sequence[float], k: int) -> float:
    """Return normalized discounted cumulative gain at k.

    Relevance grades are converted to gains with ``2**grade - 1``. The ideal
    ranking sorts the available grades from highest to lowest.
    """
    _validate_k(k)

    def discounted_gain(score: float, rank: int) -> float:
        gain = (2**score) - 1
        return gain / math.log2(rank + 1)

    actual = relevance[:k]
    ideal = sorted(relevance, reverse=True)[:k]
    dcg = sum(discounted_gain(score, rank) for rank, score in enumerate(actual, start=1))
    idcg = sum(discounted_gain(score, rank) for rank, score in enumerate(ideal, start=1))
    return dcg / idcg if idcg else 0.0


def evaluate_ranking(
    relevance: Sequence[float],
    *,
    total_relevant: int,
    k: int,
) -> RankingMetrics:
    """Calculate all supported metrics for one query's ranked results."""
    return RankingMetrics(
        precision=precision_at_k(relevance, k),
        recall=recall_at_k(relevance, total_relevant, k),
        reciprocal_rank=reciprocal_rank(relevance, k),
        ndcg=ndcg_at_k(relevance, k),
    )
