"""Aggregate comparable reranker training reports across random seeds."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


def summarize_reports(reports: list[dict[str, Any]], *, split: str = "test") -> dict[str, Any]:
    if len(reports) < 2:
        raise ValueError("At least two seed reports are required")
    query_sets = {tuple(report["query_splits"][split]) for report in reports}
    if len(query_sets) != 1:
        raise ValueError(f"All reports must use the same {split} query split")
    values = [float(report["metrics"][split]["reranker_ndcg_at_10"]) for report in reports]
    baseline_values = [float(report["metrics"][split]["baseline_ndcg_at_10"]) for report in reports]
    recall_values = [float(report["metrics"][split]["reranker_recall_at_3"]) for report in reports]
    baseline_recall_values = [float(report["metrics"][split]["baseline_recall_at_3"]) for report in reports]
    return {
        "split": split,
        "evaluation_supervision": reports[0].get("evaluation_supervision", {}).get(split, "unknown"),
        "queries": list(query_sets.pop()),
        "seeds": [int(report["seed"]) for report in reports],
        "baseline_ndcg_at_10": statistics.fmean(baseline_values),
        "reranker_ndcg_at_10_by_seed": values,
        "reranker_ndcg_at_10_mean": statistics.fmean(values),
        "reranker_ndcg_at_10_sample_std": statistics.stdev(values),
        "baseline_recall_at_3": statistics.fmean(baseline_recall_values),
        "reranker_recall_at_3_by_seed": recall_values,
        "reranker_recall_at_3_mean": statistics.fmean(recall_values),
        "reranker_recall_at_3_sample_std": statistics.stdev(recall_values),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--split", default="test", choices=("validation", "test"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize_reports([json.loads(path.read_text(encoding="utf-8")) for path in args.reports], split=args.split)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
