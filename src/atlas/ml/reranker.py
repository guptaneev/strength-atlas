"""Stable inference boundary for the Phase 7 cross-encoder implementation.

No model is loaded here.  A fine-tuned transformer will implement this small
contract, allowing the API/search layer to remain independent of Hugging Face.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from atlas.ml.training import TransformerScorer


@dataclass(frozen=True)
class RerankCandidate:
    """A retrievable item, whether it is a program or source-backed evidence."""

    candidate_id: int
    text: str
    candidate_type: str = "program"


class Reranker(Protocol):
    """Score query/candidate pairs; larger scores indicate better relevance."""

    def score(self, query: str, candidates: Sequence[RerankCandidate]) -> list[float]: ...


def rerank_candidates(reranker: Reranker, query: str, candidates: Sequence[RerankCandidate]) -> list[RerankCandidate]:
    scores = reranker.score(query, candidates)
    if len(scores) != len(candidates):
        raise ValueError("Reranker must return exactly one score per candidate")
    return [candidate for _, candidate in sorted(zip(scores, candidates, strict=True), key=lambda pair: pair[0], reverse=True)]


class FineTunedCrossEncoder:
    """Production-facing adapter for a saved Strength Atlas model directory."""

    def __init__(self, model_path: str, *, max_length: int = 256, batch_size: int = 16) -> None:
        self._scorer = TransformerScorer(model_path, max_length=max_length)
        self._batch_size = batch_size

    def score(self, query: str, candidates: Sequence[RerankCandidate]) -> list[float]:
        return self._scorer.score(query, [candidate.text for candidate in candidates], batch_size=self._batch_size)
