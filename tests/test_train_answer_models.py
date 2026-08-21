from __future__ import annotations

import pytest

from scripts.train_answer_models import dpo_rows, sft_rows, validate_query_split


def _pair(query_id: str) -> dict:
    return {
        "query_id": query_id,
        "query": "What should I do?",
        "evidence": [{"evidence_id": "e1", "text": "Use three sessions."}],
        "chosen": {"answer": "Use three sessions. [e1]"},
        "rejected": {"answer": "Use six sessions. [e1]"},
    }


def test_training_rows_preserve_evidence_and_preferences() -> None:
    pair = _pair("train")
    assert "[e1] Use three sessions." in sft_rows([pair])[0]["messages"][1]["content"]
    assert dpo_rows([pair])[0]["chosen"][0]["content"] == "Use three sessions. [e1]"


def test_query_split_rejects_leakage() -> None:
    with pytest.raises(ValueError, match="leakage"):
        validate_query_split([_pair("same")], [_pair("same")])
