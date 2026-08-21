from types import SimpleNamespace

from atlas.ml.dataset import RelevanceDataset, RelevanceQuery
from atlas.ml.preference_export import _clean_url, _program_matches_intent, _query_overlap, export_answer_evidence


class _Session:
    def scalars(self, _statement):
        return SimpleNamespace(all=lambda: [SimpleNamespace(id=8, raw_text="Train three times weekly.", confidence=0.9)])

    def get(self, model, key):
        if model.__name__ == "Source":
            return SimpleNamespace(canonical_url="https://example.com/guide", title="Guide")
        return SimpleNamespace(id=key)


def test_export_contains_only_claims_from_retrieved_documents(monkeypatch):
    response = SimpleNamespace(evidence=[SimpleNamespace(source_id=4, document_id=5)], program_candidates=[])
    monkeypatch.setattr("atlas.ml.preference_export.run_retrieval_debug", lambda *_args, **_kwargs: response)
    monkeypatch.setattr("atlas.ml.preference_export.search_programs", lambda *_args, **_kwargs: [])
    dataset = RelevanceDataset(1, "draft", "program_with_metadata_v1", [RelevanceQuery("q1", "three day program", {}, [])])

    exported = export_answer_evidence(_Session(), dataset)

    assert exported["query_count"] == 1
    assert exported["queries"][0]["evidence"] == [{
        "evidence_id": "claim-8",
        "claim_id": 8,
        "canonical_url": "https://example.com/guide",
        "source_title": "Guide",
        "text": "Train three times weekly.",
    }]


def test_query_overlap_rejects_unrelated_claims_and_keeps_matching_terms():
    assert _query_overlap("beginner powerlifting program four days", "A beginner program uses four training days.") == 3
    assert _query_overlap("beginner powerlifting program four days", "Olympic lifting can improve jumping performance.") == 0


def test_program_export_requires_every_explicit_structured_constraint():
    matching = SimpleNamespace(days_per_week=4, experience_level="beginner", split_type="full body")
    wrong_days = SimpleNamespace(days_per_week=3, experience_level="beginner", split_type="full body")

    intent = {"days_per_week": 4, "experience_level": "beginner"}
    assert _program_matches_intent(matching, intent) is True
    assert _program_matches_intent(wrong_days, intent) is False


def test_clean_url_unwraps_markdown_url():
    assert _clean_url("[https://example.com/guide](https://example.com/guide)") == "https://example.com/guide"
