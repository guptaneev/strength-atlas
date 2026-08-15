import pytest

from atlas.search.metrics import (
    evaluate_ranking,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_binary_ranking_metrics() -> None:
    relevance = [0, 3, 1, 0, 2]

    assert precision_at_k(relevance, k=5) == pytest.approx(0.6)
    assert recall_at_k(relevance, total_relevant=3, k=5) == pytest.approx(1.0)
    assert reciprocal_rank(relevance) == pytest.approx(0.5)


def test_ndcg_rewards_relevant_results_near_the_top() -> None:
    poorly_ordered = [0, 3, 1]
    ideally_ordered = [3, 1, 0]

    assert ndcg_at_k(ideally_ordered, k=3) == pytest.approx(1.0)
    assert ndcg_at_k(poorly_ordered, k=3) == pytest.approx(0.6443, abs=1e-3)


def test_metrics_handle_no_relevant_results() -> None:
    relevance = [0, 0, 0]

    assert precision_at_k(relevance, k=3) == 0.0
    assert recall_at_k(relevance, total_relevant=0, k=3) == 0.0
    assert reciprocal_rank(relevance) == 0.0
    assert ndcg_at_k(relevance, k=3) == 0.0


def test_metrics_reject_invalid_k() -> None:
    with pytest.raises(ValueError):
        precision_at_k([1], k=0)


def test_ranking_comparison_exposes_rank_quality() -> None:
    later_relevant = evaluate_ranking([0, 3, 1, 0, 2], total_relevant=3, k=5)
    ideal_order = evaluate_ranking([3, 2, 1, 0, 0], total_relevant=3, k=5)

    assert later_relevant.precision == ideal_order.precision == pytest.approx(0.6)
    assert later_relevant.recall == ideal_order.recall == pytest.approx(1.0)
    assert later_relevant.reciprocal_rank == pytest.approx(0.5)
    assert ideal_order.reciprocal_rank == pytest.approx(1.0)
    assert later_relevant.ndcg < ideal_order.ndcg
    assert ideal_order.ndcg == pytest.approx(1.0)
