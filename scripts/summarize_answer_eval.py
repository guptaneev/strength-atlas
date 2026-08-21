"""Summarize citation and verbosity checks for generated answer candidates."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import statistics
from typing import Any


CITATION_RE = re.compile(r"\[(e\d+)\]")


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_model[row["model"]].append(row)

    models: dict[str, Any] = {}
    for model, rows in sorted(by_model.items()):
        valid: list[float] = []
        presence: list[float] = []
        gold_recall: list[float] = []
        words: list[int] = []
        for row in rows:
            cited = set(CITATION_RE.findall(row.get("answer", "")))
            allowed = set(row.get("evidence_ids", []))
            gold = set(row.get("gold_citations", []))
            valid.append(float(cited <= allowed))
            presence.append(float(bool(cited)))
            if gold:
                gold_recall.append(len(cited & gold) / len(gold))
            words.append(len(row.get("answer", "").split()))
        models[model] = {
            "queries": len(rows),
            "citation_validity": statistics.fmean(valid),
            "citation_presence": statistics.fmean(presence),
            "gold_citation_recall_nonempty": statistics.fmean(gold_recall) if gold_recall else None,
            "gold_citation_queries": len(gold_recall),
            "mean_answer_words": statistics.fmean(words),
        }

    dpo = [values for name, values in models.items() if name.startswith("dpo-")]
    dpo_aggregate = None
    if dpo:
        fields = ("citation_validity", "citation_presence", "gold_citation_recall_nonempty", "mean_answer_words")
        dpo_aggregate = {
            field: {
                "mean": statistics.fmean(row[field] for row in dpo),
                "sample_std": statistics.stdev(row[field] for row in dpo) if len(dpo) > 1 else 0.0,
            }
            for field in fields
        }

    base_by_query = {row["query_id"]: row.get("answer", "") for row in by_model.get("base", [])}
    exact_base_matches = {
        model: sum(row.get("answer", "") == base_by_query.get(row["query_id"]) for row in rows)
        for model, rows in by_model.items()
        if model != "base"
    }
    return {
        "records": len(records),
        "queries": len({row["query_id"] for row in records}),
        "models": models,
        "dpo_seed_aggregate": dpo_aggregate,
        "exact_base_answer_matches": exact_base_matches,
        "limitations": [
            "These are mechanical citation and length checks, not human preference judgments.",
            "Gold-citation recall measures overlap with the preferred answer's citations, not factual correctness.",
            "Only five held-out queries were generated; blind human review is still required.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = json.loads(args.input.read_text(encoding="utf-8"))
    report = summarize(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
