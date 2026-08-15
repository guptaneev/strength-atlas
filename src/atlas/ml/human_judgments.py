"""Apply reviewer judgments without overwriting the bootstrap label source."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from atlas.ml.dataset import RelevanceDataset, RelevanceQuery


def load_human_judgments(path: str | Path) -> dict[tuple[str, int], int]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    judgments: dict[tuple[str, int], int] = {}
    for row in raw.get("judgments", []):
        query_id = str(row["query_id"])
        program_id = int(row["program_id"])
        relevance = int(row["relevance"])
        if relevance not in {0, 1, 2, 3}:
            raise ValueError("Human relevance grades must be between 0 and 3")
        key = (query_id, program_id)
        if key in judgments:
            raise ValueError(f"Duplicate human judgment: {key}")
        judgments[key] = relevance
    return judgments


def apply_human_judgments(dataset: RelevanceDataset, judgments: dict[tuple[str, int], int]) -> RelevanceDataset:
    """Return a dataset whose matching program grades come from the reviewer."""
    found: set[tuple[str, int]] = set()
    queries: list[RelevanceQuery] = []
    for query in dataset.queries:
        candidates = []
        for candidate in query.candidates:
            key = (query.query_id, candidate.program_id) if candidate.program_id is not None else None
            if key is not None and key in judgments:
                candidates.append(replace(candidate, relevance=judgments[key], reason="human_authoritative_v1"))
                found.add(key)
            else:
                candidates.append(candidate)
        queries.append(replace(query, candidates=candidates))
    missing = set(judgments) - found
    if missing:
        raise ValueError(f"Human judgments do not match the dataset: {sorted(missing)}")
    return RelevanceDataset(dataset.version, dataset.status, dataset.document_representation, queries)
