"""Versioned, human-reviewable relevance-dataset contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RELEVANCE_SCALE = {
    "0": "Irrelevant to the query intent.",
    "1": "Marginally relevant; shares a topic but misses the main constraints.",
    "2": "Useful match; satisfies part of the intent but misses an important constraint.",
    "3": "Excellent match; directly satisfies the query intent.",
}
VALID_STATUSES = {"draft", "frozen"}
VALID_CANDIDATE_COLLECTIONS = {"program", "source_evidence"}


@dataclass(frozen=True)
class CandidateJudgment:
    program_id: int | None
    canonical_url: str | None
    candidate_source: str
    baseline_rank: int | None
    baseline_score: float | None
    relevance: int | None
    reason: str | None
    source_id: int | None = None

    @property
    def key(self) -> str:
        if self.program_id is not None:
            return f"program:{self.program_id}"
        if self.source_id is not None:
            return f"source:{self.source_id}"
        if self.canonical_url:
            return f"url:{self.canonical_url}"
        raise ValueError("Candidate requires program_id, source_id, or canonical_url")


@dataclass(frozen=True)
class RelevanceQuery:
    query_id: str
    query: str
    intent: dict[str, Any]
    candidates: list[CandidateJudgment]
    candidate_collection: str = "program"


@dataclass(frozen=True)
class RelevanceDataset:
    version: int
    status: str
    document_representation: str
    queries: list[RelevanceQuery]

    def validate(self, *, require_complete_judgments: bool = False) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Dataset status must be one of {sorted(VALID_STATUSES)}")
        query_ids: set[str] = set()
        for query in self.queries:
            if not query.query_id or not query.query:
                raise ValueError("Each query requires query_id and query")
            if query.candidate_collection not in VALID_CANDIDATE_COLLECTIONS:
                raise ValueError(f"Unknown candidate collection: {query.candidate_collection}")
            if query.query_id in query_ids:
                raise ValueError(f"Duplicate query_id: {query.query_id}")
            query_ids.add(query.query_id)
            candidate_keys: set[str] = set()
            for candidate in query.candidates:
                if candidate.key in candidate_keys:
                    raise ValueError(f"Duplicate candidate for query {query.query_id}: {candidate.key}")
                candidate_keys.add(candidate.key)
                if candidate.relevance is not None and candidate.relevance not in {0, 1, 2, 3}:
                    raise ValueError("Relevance grades must be integers from 0 through 3")
                if require_complete_judgments and candidate.relevance is None:
                    raise ValueError(f"Unjudged candidate in query {query.query_id}: {candidate.key}")
        if self.status == "frozen" and not require_complete_judgments:
            self.validate(require_complete_judgments=True)


def load_dataset(path: str | Path, *, require_complete_judgments: bool = False) -> RelevanceDataset:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("queries"), list):
        raise ValueError("Dataset must contain a top-level queries array")
    queries: list[RelevanceQuery] = []
    for item in raw["queries"]:
        if not isinstance(item, dict):
            raise ValueError("Each query must be an object")
        candidates: list[CandidateJudgment] = []
        for candidate in item.get("candidates", []):
            if not isinstance(candidate, dict):
                raise ValueError("Each candidate must be an object")
            relevance = candidate.get("relevance")
            candidates.append(
                CandidateJudgment(
                    program_id=_as_int(candidate.get("program_id")),
                    canonical_url=_as_str(candidate.get("canonical_url") or candidate.get("url")),
                    candidate_source=str(candidate.get("candidate_source") or "manual"),
                    baseline_rank=_as_int(candidate.get("baseline_rank")),
                    baseline_score=_as_float(candidate.get("baseline_score")),
                    relevance=_as_int(relevance),
                    reason=_as_str(candidate.get("reason")),
                    source_id=_as_int(candidate.get("source_id")),
                )
            )
        intent = item.get("intent")
        queries.append(
            RelevanceQuery(
                query_id=str(item.get("query_id") or ""),
                query=str(item.get("query") or ""),
                intent=intent if isinstance(intent, dict) else {},
                candidates=candidates,
                candidate_collection=str(item.get("candidate_collection") or "program"),
            )
        )
    dataset = RelevanceDataset(
        version=int(raw.get("version", 1)),
        status=str(raw.get("status") or "draft"),
        document_representation=str(raw.get("document_representation") or "program_with_metadata_v1"),
        queries=queries,
    )
    dataset.validate(require_complete_judgments=require_complete_judgments)
    return dataset


def save_dataset(dataset: RelevanceDataset, path: str | Path) -> None:
    dataset.validate()
    payload = {
        "version": dataset.version,
        "status": dataset.status,
        "document_representation": dataset.document_representation,
        "relevance_scale": RELEVANCE_SCALE,
        "queries": [
            {
                "query_id": query.query_id,
                "query": query.query,
                "intent": query.intent,
                "candidate_collection": query.candidate_collection,
                "candidates": [
                    {
                        "program_id": c.program_id,
                        "canonical_url": c.canonical_url,
                        "candidate_source": c.candidate_source,
                        "baseline_rank": c.baseline_rank,
                        "baseline_score": c.baseline_score,
                        "relevance": c.relevance,
                        "reason": c.reason,
                        "source_id": c.source_id,
                    }
                    for c in query.candidates
                ],
            }
            for query in dataset.queries
        ],
    }
    Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _as_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _as_str(value: Any) -> str | None:
    return str(value) if value is not None else None
