from scripts.build_blind_answer_review import build_packet


def test_build_packet_hides_models_and_keeps_key_separate() -> None:
    records = [
        {"query_id": "q1", "model": "base", "answer": "Base [e1]."},
        {"query_id": "q1", "model": "dpo", "answer": "DPO [e1]."},
    ]
    split = {
        "pairs": [
            {
                "query_id": "q1",
                "query": "Question?",
                "evidence": [{"evidence_id": "e1", "text": "Evidence."}],
            }
        ]
    }

    packet, key = build_packet(records, split, seed=7)

    assert packet["review_id"] == key["review_id"]
    assert "model" not in packet["queries"][0]["candidates"][0]
    assert {entry["model"] for entry in key["entries"]} == {"base", "dpo"}
    assert packet["queries"][0]["evidence"][0]["evidence_id"] == "e1"
