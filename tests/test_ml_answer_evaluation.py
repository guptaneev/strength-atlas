from atlas.ml.answer_evaluation import evaluate_answer, evaluate_answer_records, extract_citations, summarize_human_review


def test_extract_citations_preserves_order_and_deduplicates():
    assert extract_citations("Use [e2], then [e1]. [e2]") == ["e2", "e1"]


def test_evaluate_answer_rejects_unknown_citations_and_tracks_verbosity():
    result = evaluate_answer(
        "Use three sessions [e1] [e9].",
        ["e1", "e2"],
        gold_citations=["e1"],
        reference_answer="Use three sessions.",
    )
    assert result["citation_format_valid"] is False
    assert result["citation_precision"] == 0.5
    assert result["gold_citation_recall"] == 1.0
    assert result["longer_than_reference"] is True


def test_aggregate_keeps_human_and_assisted_results_separate():
    report = evaluate_answer_records([
        {"answer": "Use [e1].", "evidence_ids": ["e1"], "label_source": "human"},
        {"answer": "Use [e2].", "evidence_ids": ["e1"], "label_source": "model_assisted"},
    ])
    assert report["overall"]["answers"] == 2
    assert report["human"]["citation_format_valid_rate"] == 1.0
    assert report["model_assisted"]["citation_format_valid_rate"] == 0.0


def test_aggregate_can_compare_models():
    report = evaluate_answer_records([
        {"answer": "Use [e1].", "evidence_ids": ["e1"], "model": "base"},
        {"answer": "Use [e2].", "evidence_ids": ["e1"], "model": "dpo-seed42"},
    ])
    assert report["by_model"]["base"]["citation_format_valid_rate"] == 1.0
    assert report["by_model"]["dpo-seed42"]["citation_format_valid_rate"] == 0.0


def test_human_review_summary_applies_query_judgments_by_model():
    report = summarize_human_review(
        [
            {"query_id": "q1", "model": "base"},
            {"query_id": "q1", "model": "dpo-seed42"},
            {"query_id": "q2", "model": "base"},
        ],
        [
            {"query_id": "q1", "decision": "approve", "applies_to_models": ["base", "dpo-seed42"]},
            {"query_id": "q2", "decision": "reject", "applies_to_models": ["base"]},
        ],
    )
    assert report["overall"]["approval_rate"] == 2 / 3
    assert report["by_model"]["base"]["approval_rate"] == 0.5
    assert report["overall"]["bootstrap_query_approval_rate_95_ci"] == [0.0, 1.0]
