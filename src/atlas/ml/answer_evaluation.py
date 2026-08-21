"""Deterministic evaluation helpers for evidence-grounded generated answers.

These metrics validate the citation contract and make verbosity measurable.
They do not claim semantic entailment: semantic groundedness still requires a
human or model-assisted review pass over the cited claims.
"""

from __future__ import annotations

import re
import random
from statistics import fmean, median
from typing import Any, Iterable


_CITATION = re.compile(r"\[([^\[\]]+)\]")


def extract_citations(answer: str) -> list[str]:
    """Return citation IDs in appearance order, without duplicates."""
    seen: set[str] = set()
    citations: list[str] = []
    for value in _CITATION.findall(answer):
        citation = value.strip()
        if citation and citation not in seen:
            seen.add(citation)
            citations.append(citation)
    return citations


def evaluate_answer(
    answer: str,
    evidence_ids: Iterable[str],
    *,
    gold_citations: Iterable[str] | None = None,
    reference_answer: str | None = None,
) -> dict[str, Any]:
    """Evaluate one answer against the evidence IDs supplied to the model."""
    citations = extract_citations(answer)
    evidence = {str(item) for item in evidence_ids}
    known = [citation for citation in citations if citation in evidence]
    result: dict[str, Any] = {
        "citations": citations,
        "citation_format_valid": bool(citations) and len(known) == len(citations),
        "citation_precision": len(known) / len(citations) if citations else 0.0,
        "citation_count": len(citations),
        "word_count": len(answer.split()),
    }
    if gold_citations is not None:
        gold = {str(item) for item in gold_citations}
        result["gold_citation_recall"] = len(set(known) & gold) / len(gold) if gold else 1.0
    if reference_answer is not None:
        reference_words = len(reference_answer.split())
        result["reference_word_count"] = reference_words
        result["verbosity_ratio"] = len(answer.split()) / reference_words if reference_words else None
        result["longer_than_reference"] = len(answer.split()) > reference_words
    return result


def evaluate_answer_records(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate answer metrics while preserving human/assisted populations."""
    rows = list(records)
    if not rows:
        raise ValueError("At least one answer record is required")
    evaluated: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row.get("answer"), str):
            raise ValueError("Each answer record requires an answer string")
        metrics = evaluate_answer(
            row["answer"],
            row.get("evidence_ids", []),
            gold_citations=row.get("gold_citations"),
            reference_answer=row.get("reference_answer"),
        )
        metrics["label_source"] = row.get("label_source", "unknown")
        metrics["model"] = row.get("model", "unknown")
        if "query_id" in row:
            metrics["query_id"] = row["query_id"]
        evaluated.append(metrics)

    def aggregate(subset: list[dict[str, Any]]) -> dict[str, Any]:
        if not subset:
            return {"answers": 0}
        return {
            "answers": len(subset),
            "citation_format_valid_rate": fmean(item["citation_format_valid"] for item in subset),
            "citation_precision": fmean(item["citation_precision"] for item in subset),
            "mean_word_count": fmean(item["word_count"] for item in subset),
            "median_word_count": median(item["word_count"] for item in subset),
            "longer_than_reference_rate": (
                fmean(item["longer_than_reference"] for item in subset)
                if any("longer_than_reference" in item for item in subset)
                else None
            ),
            "mean_verbosity_ratio": (
                fmean(item["verbosity_ratio"] for item in subset if item.get("verbosity_ratio") is not None)
                if any(item.get("verbosity_ratio") is not None for item in subset)
                else None
            ),
        }

    by_model = {
        str(model): aggregate([item for item in evaluated if item["model"] == model])
        for model in sorted({item["model"] for item in evaluated})
    }
    return {
        "answers": len(evaluated),
        "overall": aggregate(evaluated),
        "human": aggregate([item for item in evaluated if item["label_source"] == "human"]),
        "model_assisted": aggregate([item for item in evaluated if item["label_source"] == "model_assisted"]),
        "by_model": by_model,
    }


def summarize_human_review(
    records: Iterable[dict[str, Any]], judgments: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """Apply query-level human judgments and summarize approval by model."""
    judgment_map = {str(item["query_id"]): item for item in judgments}
    rows: list[dict[str, Any]] = []
    for record in records:
        query_id = str(record.get("query_id", ""))
        judgment = judgment_map.get(query_id)
        if judgment is None:
            continue
        models = judgment.get("applies_to_models")
        if models and record.get("model") not in models:
            continue
        decision = str(judgment.get("decision", "")).lower()
        rows.append({
            "model": record.get("model", "unknown"),
            "query_id": query_id,
            "approved": decision.startswith("approve"),
            "decision": judgment.get("decision"),
        })

    def aggregate(subset: list[dict[str, Any]]) -> dict[str, Any]:
        query_values = {
            item["query_id"]: item["approved"] for item in subset
        }
        bootstrap = _bootstrap_rate(list(query_values.values()))
        return {
            "answers": len(subset),
            "approved": sum(item["approved"] for item in subset),
            "approval_rate": (
                sum(item["approved"] for item in subset) / len(subset) if subset else None
            ),
            "bootstrap_query_approval_rate_95_ci": bootstrap,
        }

    return {
        "reviewed_answers": len(rows),
        "overall": aggregate(rows),
        "by_model": {
            str(model): aggregate([item for item in rows if item["model"] == model])
            for model in sorted({item["model"] for item in rows})
        },
        "decisions": rows,
    }


def _bootstrap_rate(values: list[bool], *, iterations: int = 1000, seed: int = 42) -> list[float] | None:
    """Return a percentile bootstrap interval over query-level boolean labels."""
    if not values:
        return None
    rng = random.Random(seed)
    samples = [
        sum(rng.choice(values) for _ in values) / len(values)
        for _ in range(iterations)
    ]
    samples.sort()
    return [samples[int(iterations * 0.025)], samples[int(iterations * 0.975) - 1]]
