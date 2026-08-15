"""Stable inference boundary for the Phase 7 cross-encoder implementation.

No model is loaded here.  A fine-tuned transformer will implement this small
contract, allowing the API/search layer to remain independent of Hugging Face.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class RerankCandidate:
    program_id: int
    text: str


class Reranker(Protocol):
    """Score query/candidate pairs; larger scores indicate better relevance."""

    def score(self, query: str, candidates: Sequence[RerankCandidate]) -> list[float]: ...


def rerank_candidates(reranker: Reranker, query: str, candidates: Sequence[RerankCandidate]) -> list[RerankCandidate]:
    scores = reranker.score(query, candidates)
    if len(scores) != len(candidates):
        raise ValueError("Reranker must return exactly one score per candidate")
    return [candidate for _, candidate in sorted(zip(scores, candidates, strict=True), key=lambda pair: pair[0], reverse=True)]
