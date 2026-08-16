from __future__ import annotations

import pytest

from atlas.ml.training import _split_query_ids


def test_fixed_evaluation_split_keeps_new_authoritative_queries_in_training() -> None:
    splits = _split_query_ids(
        ["train", "validation", "test", "new_human_query"],
        seed=42,
        authoritative_query_ids={"new_human_query"},
        fixed_evaluation_query_ids={"validation": {"validation"}, "test": {"test"}},
    )
    assert splits == {
        "train": {"train", "new_human_query"},
        "validation": {"validation"},
        "test": {"test"},
    }


def test_fixed_evaluation_split_rejects_label_leakage() -> None:
    with pytest.raises(ValueError, match="overlap"):
        _split_query_ids(
            ["train", "test"],
            seed=42,
            authoritative_query_ids={"test"},
            fixed_evaluation_query_ids={"validation": set(), "test": {"test"}},
        )
