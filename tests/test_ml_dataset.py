import json

import pytest

from atlas.ml.dataset import CandidateJudgment, RelevanceDataset, RelevanceQuery, load_dataset, save_dataset
from atlas.ml.error_analysis import make_error_analysis_template, summarize_error_analysis
from atlas.ml.reranker import RerankCandidate, rerank_candidates
from atlas.ml.splits import split_queries


def _dataset(status: str = "draft") -> RelevanceDataset:
    return RelevanceDataset(
        version=1,
        status=status,
        document_representation="program_with_metadata_v1",
        queries=[
            RelevanceQuery(f"q{i}", f"query {i}", {}, [CandidateJudgment(i, None, "baseline", 1, None, 3, None)])
            for i in range(1, 11)
        ],
    )


def test_query_split_is_reproducible_and_has_no_query_leakage() -> None:
    dataset = _dataset()
    first = split_queries(dataset, seed=9)
    second = split_queries(dataset, seed=9)
    assert first == second
    assert set(first.train_query_ids).isdisjoint(first.validation_query_ids)
    assert set(first.train_query_ids).isdisjoint(first.test_query_ids)
    assert set(first.train_query_ids + first.validation_query_ids + first.test_query_ids) == {f"q{i}" for i in range(1, 11)}


def test_frozen_dataset_cannot_have_unjudged_candidates() -> None:
    dataset = RelevanceDataset(1, "frozen", "program_with_metadata_v1", [
        RelevanceQuery("q1", "query", {}, [CandidateJudgment(1, None, "baseline", 1, None, None, None)])
    ])
    with pytest.raises(ValueError, match="Unjudged"):
        dataset.validate()


def test_loads_legacy_url_and_round_trips_to_canonical_url(tmp_path) -> None:
    path = tmp_path / "data.json"
    path.write_text(json.dumps({"status": "draft", "queries": [{"query_id": "q", "query": "bench", "candidates": [{"url": "https://example.com", "relevance": 1}]}]}), encoding="utf-8")
    dataset = load_dataset(path)
    assert dataset.queries[0].candidates[0].canonical_url == "https://example.com"
    save_dataset(dataset, path)
    assert "canonical_url" in path.read_text(encoding="utf-8")


def test_reranker_contract_orders_larger_scores_first() -> None:
    class _Reranker:
        def score(self, _query, _candidates):
            return [0.1, 0.9]

    ranked = rerank_candidates(_Reranker(), "bench", [RerankCandidate(1, "a"), RerankCandidate(2, "b")])
    assert [candidate.program_id for candidate in ranked] == [2, 1]


def test_error_analysis_template_and_summary() -> None:
    template = make_error_analysis_template({"queries": [{"query_id": "q", "query": "bench", "ranking": []}]})
    template["reviews"][0]["category"] = "frequency_mismatch"
    summary = summarize_error_analysis(template)
    assert summary["category_counts"] == {"frequency_mismatch": 1}
