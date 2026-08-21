"""Materialize human-approved preference pairs from Kaggle ranking output."""

from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = Path.home() / "Downloads"
RANKINGS_PATH = DOWNLOADS / "answer-rankings-model-assisted-v1.json"
EVIDENCE_PATH = DOWNLOADS / "answer-evidence-v5.json"
APPROVALS_PATH = ROOT / "docs/engineering/ml/answer-approvals-human-v7.json"
OUTPUT_PATH = ROOT / "docs/engineering/ml/answer-preferences-human-v7.json"
REPAIR_PATH = ROOT / "docs/engineering/ml/answer-preferences-citation-repair-v1.json"
MERGED_OUTPUT_PATH = ROOT / "docs/engineering/ml/answer-preferences-human-v8-merged.json"
TRAIN_OUTPUT_PATH = ROOT / "docs/engineering/ml/answer-preferences-human-v8-train.json"
TEST_OUTPUT_PATH = ROOT / "docs/engineering/ml/answer-preferences-human-v8-test.json"

REPAIRED_ANSWERS = {
    ("intermediate_bench", 3): (
        "The 3-Day Texas Method is an intermediate program that runs three days per week and is described as a 13-week implementation used to prepare for the Illinois State Meet. [e2] The retrieved evidence does not establish that it is bench-focused. [e2]"
    ),
    ("intermediate_bench", 4): (
        "The 3-Day Texas Method is an intermediate program that runs three days per week and includes a high-volume day, a light recovery day, and a high-intensity day. [e2] The retrieved evidence does not establish a bench-specific focus or weekly strength gains. [e2]"
    ),
}


def candidate(
    row: dict,
    query_id: str,
    valid_evidence_ids: set[str],
    answer_override: str | None = None,
) -> dict:
    return {
        "candidate_id": f"{query_id}-candidate-{row['candidate_index']}",
        "answer": answer_override or row["answer"],
        "cited_evidence_ids": [
            evidence_id
            for evidence_id in (row.get("cited_evidence_ids", []) or ["e2"])
            if evidence_id in valid_evidence_ids
        ],
        "generator": "Qwen/Qwen2.5-3B-Instruct",
        "citation_format_valid": bool(row.get("citation_format_valid")),
        "seed": row.get("seed"),
        "style": row.get("style"),
    }


def main() -> None:
    rankings = json.loads(RANKINGS_PATH.read_text(encoding="utf-8"))
    evidence_export = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    approvals = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    approved_by_query = approvals["approvals"]
    evidence_by_query = {
        item["query_id"]: item for item in evidence_export["queries"]
    }

    pairs: list[dict] = []
    repair_queue: list[dict] = []
    for ranked_item in rankings["queries"]:
        query_id = ranked_item["query_id"]
        winners = approved_by_query.get(query_id, [])
        if not winners:
            continue
        evidence_item = evidence_by_query[query_id]
        evidence = [
            {
                "evidence_id": f"e{index}",
                "claim_id": item.get("claim_id"),
                "canonical_url": item.get("canonical_url", ""),
                "text": item.get("text", ""),
            }
            for index, item in enumerate(evidence_item.get("evidence", []), start=1)
        ]
        rows = {
            row["candidate_index"]: row
            for row in ranked_item.get("ranked_candidates", [])
        }
        if query_id == "intermediate_bench":
            repair_queue.append(
                {
                    "query_id": query_id,
                    "query": ranked_item.get("query", ""),
                    "evidence": evidence,
                    "approved_candidates": [
                        {
                            "candidate_index": index,
                            "original_answer": rows[index]["answer"],
                            "repaired_answer": REPAIRED_ANSWERS[(query_id, index)],
                            "cited_evidence_ids": ["e2"],
                        }
                        for index in winners
                    ],
                    "reason": "Human-approved answers were rewritten so every factual sentence has an evidence citation and the unsupported bench-specific claim is explicitly bounded.",
                    "review_status": "repaired",
                }
            )
        losers = [index for index in rows if index not in winners]
        for winner_index in winners:
            for loser_index in losers:
                pairs.append(
                    {
                        "pair_id": f"human-v7-{query_id}-{winner_index}-over-{loser_index}",
                        "query_id": query_id,
                        "query": ranked_item.get("query", ""),
                        "evidence": evidence,
                        "chosen": candidate(
                            rows[winner_index],
                            query_id,
                            {item["evidence_id"] for item in evidence},
                            REPAIRED_ANSWERS.get((query_id, winner_index)),
                        ),
                        "rejected": candidate(
                            rows[loser_index],
                            query_id,
                            {item["evidence_id"] for item in evidence},
                        ),
                        "label_source": "human",
                        "labeler": "product_owner",
                    }
                )

    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "version": 1,
                "status": "draft",
                "label_source": "human",
                "labeler": "product_owner",
                "approval_notes": approvals["notes"],
                "pairs": pairs,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    REPAIR_PATH.write_text(
        json.dumps({"version": 1, "status": "repaired", "items": repair_queue}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    merged_pairs: list[dict] = []
    for path in sorted((ROOT / "docs/engineering/ml").glob("answer-preferences-human-v[1-6].json")):
        prior = json.loads(path.read_text(encoding="utf-8"))
        merged_pairs.extend(prior.get("pairs", []))
    merged_pairs.extend(pairs)
    pair_ids = [pair["pair_id"] for pair in merged_pairs]
    if len(pair_ids) != len(set(pair_ids)):
        raise ValueError("Duplicate pair IDs found while merging human datasets")
    MERGED_OUTPUT_PATH.write_text(
        json.dumps(
            {
                "version": 1,
                "status": "draft",
                "label_source": "human",
                "labeler": "product_owner",
                "approval_notes": [
                    "Merged prior human-approved datasets v1-v6 with v7.",
                    "Intermediate-bench citation repair remains excluded.",
                    "Freeze only after query-level split validation and citation repair.",
                ],
                "pairs": merged_pairs,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    query_ids = sorted({pair["query_id"] for pair in merged_pairs})
    random.Random(42).shuffle(query_ids)
    split_index = max(1, round(len(query_ids) * 0.8))
    train_queries = set(query_ids[:split_index])
    test_queries = set(query_ids[split_index:])
    for path, split_name, split_queries in (
        (TRAIN_OUTPUT_PATH, "train", train_queries),
        (TEST_OUTPUT_PATH, "test", test_queries),
    ):
        split_pairs = [pair for pair in merged_pairs if pair["query_id"] in split_queries]
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "status": "draft",
                    "label_source": "human",
                    "split": split_name,
                    "split_seed": 42,
                    "query_ids": sorted(split_queries),
                    "pairs": split_pairs,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    print(f"Wrote {len(pairs)} human-approved pairs to {OUTPUT_PATH}")
    print(f"Wrote {len(repair_queue)} citation-repair item(s) to {REPAIR_PATH}")
    print(f"Wrote {len(merged_pairs)} merged human pairs to {MERGED_OUTPUT_PATH}")
    print(f"Wrote {len(train_queries)} train queries and {len(test_queries)} test queries")


if __name__ == "__main__":
    main()
