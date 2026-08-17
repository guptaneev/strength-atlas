from __future__ import annotations

import pytest

from atlas.ml.training import bootstrap_mean_confidence_interval


def test_bootstrap_interval_is_deterministic_and_contains_mean() -> None:
    interval = bootstrap_mean_confidence_interval([0.2, 0.4, 0.8, 1.0], iterations=1000, seed=42)
    assert interval == bootstrap_mean_confidence_interval([0.2, 0.4, 0.8, 1.0], iterations=1000, seed=42)
    assert interval["lower"] <= 0.6 <= interval["upper"]
    assert interval["iterations"] == 1000


def test_bootstrap_interval_rejects_zero_iterations() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        bootstrap_mean_confidence_interval([1.0], iterations=0)
