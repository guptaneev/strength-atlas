import json

import pytest

from atlas.ml.preferences import load_preference_dataset, preference_summary


def _pair(**overrides):
    pair = {
        "pair_id": "pair-1",
        "query_id": "query-1",
        "query": "How should I structure a novice lifting week?",
        "evidence": [{"evidence_id": "claim-1", "canonical_url": "https://example.com/guide", "text": "Train three days weekly.", "claim_id": 1}],
        "chosen": {"candidate_id": "a", "answer": "Use three days weekly [claim-1].", "cited_evidence_ids": ["claim-1"], "generator": "Qwen/Qwen2.5-3B-Instruct"},
        "rejected": {"candidate_id": "b", "answer": "Train every day.", "cited_evidence_ids": [], "generator": "Qwen/Qwen2.5-3B-Instruct"},
        "label_source": "human",
        "labeler": "product_owner",
    }
    pair.update(overrides)
    return pair


def test_preference_summary_keeps_human_and_assisted_separate(tmp_path):
    path = tmp_path / "preferences.json"
    path.write_text(json.dumps({"version": 1, "status": "draft", "pairs": [_pair(), _pair(pair_id="pair-2", label_source="model_assisted", labeler=None)]}))

    summary = preference_summary(load_preference_dataset(path))

    assert summary == {"pairs_total": 2, "human_pairs": 1, "model_assisted_pairs": 1, "human_queries": 1, "model_assisted_queries": 1}


def test_preference_dataset_rejects_citations_outside_retrieved_evidence(tmp_path):
    path = tmp_path / "preferences.json"
    invalid = _pair(chosen={"candidate_id": "a", "answer": "Unsupported", "cited_evidence_ids": ["not-retrieved"], "generator": "base"})
    path.write_text(json.dumps({"version": 1, "status": "draft", "pairs": [invalid]}))

    with pytest.raises(ValueError, match="unknown evidence"):
        load_preference_dataset(path)
