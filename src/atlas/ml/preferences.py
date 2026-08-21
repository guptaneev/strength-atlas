"""Contracts for evidence-grounded answer-preference datasets.

The preference source is intentionally explicit.  Human-reviewed pairs are the
only pairs eligible for headline evaluation; model-assisted pairs may expand
training data but must never be silently merged into that result.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


PreferenceSource = Literal["human", "model_assisted"]
VALID_SOURCES = {"human", "model_assisted"}


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    canonical_url: str
    text: str
    claim_id: int | None = None


@dataclass(frozen=True)
class AnswerCandidate:
    candidate_id: str
    answer: str
    cited_evidence_ids: list[str]
    generator: str


@dataclass(frozen=True)
class PreferencePair:
    pair_id: str
    query_id: str
    query: str
    evidence: list[EvidenceItem]
    chosen: AnswerCandidate
    rejected: AnswerCandidate
    label_source: PreferenceSource
    labeler: str | None = None


@dataclass(frozen=True)
class PreferenceDataset:
    version: int
    status: Literal["draft", "frozen"]
    pairs: list[PreferencePair]

    def validate(self) -> None:
        pair_ids: set[str] = set()
        for pair in self.pairs:
            if not pair.pair_id or pair.pair_id in pair_ids:
                raise ValueError(f"Duplicate or blank pair_id: {pair.pair_id!r}")
            pair_ids.add(pair.pair_id)
            if not pair.query_id or not pair.query.strip():
                raise ValueError(f"Pair {pair.pair_id} requires query_id and query")
            if pair.label_source not in VALID_SOURCES:
                raise ValueError(f"Pair {pair.pair_id} has an invalid label_source")
            if pair.label_source == "human" and not pair.labeler:
                raise ValueError(f"Human pair {pair.pair_id} requires a non-identifying labeler role")
            evidence_ids = [item.evidence_id for item in pair.evidence]
            if not evidence_ids or len(evidence_ids) != len(set(evidence_ids)):
                raise ValueError(f"Pair {pair.pair_id} requires uniquely identified evidence")
            for item in pair.evidence:
                if not item.canonical_url or not item.text.strip():
                    raise ValueError(f"Evidence in {pair.pair_id} requires URL and text")
            if pair.chosen.candidate_id == pair.rejected.candidate_id:
                raise ValueError(f"Pair {pair.pair_id} must contain two distinct answers")
            for candidate in (pair.chosen, pair.rejected):
                if not candidate.answer.strip() or not candidate.generator.strip():
                    raise ValueError(f"Answer in {pair.pair_id} requires text and generator")
                unknown = set(candidate.cited_evidence_ids) - set(evidence_ids)
                if unknown:
                    raise ValueError(f"Answer in {pair.pair_id} cites unknown evidence: {sorted(unknown)}")


def load_preference_dataset(path: str | Path) -> PreferenceDataset:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("pairs"), list):
        raise ValueError("Preference dataset must contain a top-level pairs array")
    pairs: list[PreferencePair] = []
    for row in payload["pairs"]:
        if not isinstance(row, dict):
            raise ValueError("Each preference pair must be an object")
        evidence = [
            EvidenceItem(
                evidence_id=str(item.get("evidence_id") or ""),
                canonical_url=str(item.get("canonical_url") or ""),
                text=str(item.get("text") or ""),
                claim_id=int(item["claim_id"]) if item.get("claim_id") is not None else None,
            )
            for item in row.get("evidence", [])
        ]
        pairs.append(PreferencePair(
            pair_id=str(row.get("pair_id") or ""),
            query_id=str(row.get("query_id") or ""),
            query=str(row.get("query") or ""),
            evidence=evidence,
            chosen=_candidate(row.get("chosen")),
            rejected=_candidate(row.get("rejected")),
            label_source=str(row.get("label_source") or ""),  # type: ignore[arg-type]
            labeler=str(row["labeler"]) if row.get("labeler") else None,
        ))
    dataset = PreferenceDataset(
        version=int(payload.get("version", 1)),
        status=str(payload.get("status") or "draft"),  # type: ignore[arg-type]
        pairs=pairs,
    )
    if dataset.status not in {"draft", "frozen"}:
        raise ValueError("Preference dataset status must be draft or frozen")
    dataset.validate()
    return dataset


def preference_summary(dataset: PreferenceDataset) -> dict[str, int]:
    dataset.validate()
    human = [pair for pair in dataset.pairs if pair.label_source == "human"]
    assisted = [pair for pair in dataset.pairs if pair.label_source == "model_assisted"]
    return {
        "pairs_total": len(dataset.pairs),
        "human_pairs": len(human),
        "model_assisted_pairs": len(assisted),
        "human_queries": len({pair.query_id for pair in human}),
        "model_assisted_queries": len({pair.query_id for pair in assisted}),
    }


def _candidate(value: object) -> AnswerCandidate:
    if not isinstance(value, dict):
        raise ValueError("Each pair requires chosen and rejected answer objects")
    citations = value.get("cited_evidence_ids", [])
    if not isinstance(citations, list):
        raise ValueError("cited_evidence_ids must be an array")
    return AnswerCandidate(
        candidate_id=str(value.get("candidate_id") or ""),
        answer=str(value.get("answer") or ""),
        cited_evidence_ids=[str(item) for item in citations],
        generator=str(value.get("generator") or ""),
    )
