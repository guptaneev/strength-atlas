from scripts.summarize_answer_eval import summarize


def test_summarize_tracks_invalid_citations_and_verbosity() -> None:
    report = summarize(
        [
            {
                "model": "base",
                "query_id": "q1",
                "answer": "Claim [e1].",
                "evidence_ids": ["e1"],
                "gold_citations": ["e1"],
            },
            {
                "model": "dpo-seed42",
                "query_id": "q1",
                "answer": "Short [e2].",
                "evidence_ids": ["e1"],
                "gold_citations": ["e1"],
            },
        ]
    )

    assert report["models"]["base"]["citation_validity"] == 1.0
    assert report["models"]["dpo-seed42"]["citation_validity"] == 0.0
    assert report["models"]["dpo-seed42"]["gold_citation_recall_nonempty"] == 0.0
    assert report["exact_base_answer_matches"]["dpo-seed42"] == 0
