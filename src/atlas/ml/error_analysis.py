"""Structured, manual baseline-error analysis artifacts."""

from __future__ import annotations

from collections import Counter
from typing import Any

ERROR_CATEGORIES = (
    "experience_level_mismatch",
    "frequency_mismatch",
    "goal_mismatch",
    "lexical_without_semantic_match",
    "multiple_constraints_not_satisfied",
    "important_metadata_ignored",
    "redundant_results",
    "partially_relevant_misranked",
    "other",
)


def make_error_analysis_template(baseline_report: dict[str, Any]) -> dict[str, Any]:
    """Make a review sheet; humans assign categories after inspecting rankings."""
    return {
        "status": "draft",
        "allowed_categories": list(ERROR_CATEGORIES),
        "reviews": [
            {
                "query_id": row["query_id"],
                "query": row["query"],
                "category": None,
                "notes": None,
                "ranking": row["ranking"],
            }
            for row in baseline_report.get("queries", [])
        ],
    }


def summarize_error_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    reviews = analysis.get("reviews", [])
    categories = [row.get("category") for row in reviews if row.get("category") in ERROR_CATEGORIES]
    counts = Counter(categories)
    total = len(categories)
    return {
        "reviewed_queries": total,
        "category_counts": dict(sorted(counts.items())),
        "category_percentages": {key: value / total if total else 0.0 for key, value in sorted(counts.items())},
        "unreviewed_queries": sum(not row.get("category") for row in reviews),
    }
