from __future__ import annotations

import pytest

from scripts.summarize_reranker_seeds import summarize_reports


def _report(seed: int, ndcg: float) -> dict:
    return {
        "seed": seed,
        "query_splits": {"test": ["q1", "q2"]},
        "evaluation_supervision": {"test": "human_authoritative"},
        "metrics": {
            "test": {
                "baseline_ndcg_at_10": 0.5,
                "reranker_ndcg_at_10": ndcg,
                "baseline_recall_at_3": 0.4,
                "reranker_recall_at_3": 0.6,
            }
        },
    }


def test_summarize_reports_calculates_seed_mean_and_sample_std() -> None:
    result = summarize_reports([_report(42, 0.6), _report(43, 0.8)])
    assert result["evaluation_supervision"] == "human_authoritative"
    assert result["reranker_ndcg_at_10_mean"] == pytest.approx(0.7)
    assert result["reranker_ndcg_at_10_sample_std"] == pytest.approx(0.1414213)


def test_summarize_reports_rejects_different_query_splits() -> None:
    second = _report(43, 0.8)
    second["query_splits"]["test"] = ["other"]
    with pytest.raises(ValueError, match="same test query split"):
        summarize_reports([_report(42, 0.6), second])
