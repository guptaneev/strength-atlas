"""Build a model-anonymous human-review packet for generated answers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import secrets
from typing import Any


def _pairs(payload: Any) -> list[dict[str, Any]]:
    rows = payload.get("pairs", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("Preference split must contain a pairs array")
    return rows


def build_packet(
    records: list[dict[str, Any]],
    split_payload: Any,
    *,
    seed: int = 42,
) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence_by_query: dict[str, dict[str, Any]] = {}
    for pair in _pairs(split_payload):
        evidence_by_query.setdefault(str(pair["query_id"]), pair)

    records_by_query: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        query_id = str(row["query_id"])
        records_by_query.setdefault(query_id, []).append(row)

    rng = random.Random(seed)
    packet_queries: list[dict[str, Any]] = []
    key_entries: list[dict[str, str]] = []
    for query_id in sorted(records_by_query):
        pair = evidence_by_query.get(query_id)
        if pair is None:
            raise ValueError(f"No preference evidence found for query {query_id}")
        candidates = list(records_by_query[query_id])
        rng.shuffle(candidates)
        public_candidates: list[dict[str, str]] = []
        for index, row in enumerate(candidates, start=1):
            candidate_id = f"{query_id}-c{index}"
            public_candidates.append({"candidate_id": candidate_id, "answer": row["answer"]})
            key_entries.append(
                {"candidate_id": candidate_id, "query_id": query_id, "model": str(row["model"])}
            )
        packet_queries.append(
            {
                "query_id": query_id,
                "query": pair["query"],
                "evidence": pair.get("evidence", []),
                "candidates": public_candidates,
                "review": {
                    "ranking_best_to_worst": [],
                    "supported_candidate_ids": [],
                    "citation_correct_candidate_ids": [],
                    "notes": "",
                },
            }
        )

    review_id = secrets.token_hex(8)
    packet = {
        "version": 1,
        "review_id": review_id,
        "instructions": [
            "Review without opening the separate model key.",
            "Rank every candidate from best to worst for each query.",
            "Mark candidates whose factual claims are supported by the supplied evidence.",
            "Mark candidates whose citations point to evidence that supports the cited claim.",
        ],
        "queries": packet_queries,
    }
    key = {"version": 1, "review_id": review_id, "entries": key_entries}
    return packet, key


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--test-split", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    packet, key = build_packet(
        json.loads(args.records.read_text(encoding="utf-8")),
        json.loads(args.test_split.read_text(encoding="utf-8")),
        seed=args.seed,
    )
    args.packet.parent.mkdir(parents=True, exist_ok=True)
    args.key.parent.mkdir(parents=True, exist_ok=True)
    args.packet.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(packet['queries'])} blind-review queries to {args.packet}")


if __name__ == "__main__":
    main()
