from __future__ import annotations

from scripts.benchmark_reranker import percentile_ms


def test_percentile_ms_uses_nearest_rank() -> None:
    assert percentile_ms([4.0, 1.0, 3.0, 2.0], 0.50) == 2.0
    assert percentile_ms([4.0, 1.0, 3.0, 2.0], 0.99) == 4.0
