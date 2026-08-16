"""Deterministic query-level train/validation/test splits."""

from __future__ import annotations

import random
from dataclasses import dataclass

from atlas.ml.dataset import RelevanceDataset


@dataclass(frozen=True)
class QuerySplits:
    seed: int
    train_query_ids: list[str]
    validation_query_ids: list[str]
    test_query_ids: list[str]

    def validate_against(self, dataset: RelevanceDataset) -> None:
        dataset_ids = {q.query_id for q in dataset.queries}
        groups = [self.train_query_ids, self.validation_query_ids, self.test_query_ids]
        assigned = [query_id for group in groups for query_id in group]
        if len(assigned) != len(set(assigned)):
            raise ValueError("A query may appear in only one split")
        if set(assigned) != dataset_ids:
            raise ValueError("Splits must assign every dataset query exactly once")


def split_queries(dataset: RelevanceDataset, *, seed: int = 42) -> QuerySplits:
    """Make a 70/15/15 query split, keeping every query in exactly one group."""
    ids = sorted(query.query_id for query in dataset.queries)
    random.Random(seed).shuffle(ids)
    total = len(ids)
    train_end = round(total * 0.70)
    validation_end = train_end + round(total * 0.15)
    # Tiny datasets still need a validation and held-out query when possible.
    if total >= 3:
        train_end = min(max(train_end, 1), total - 2)
        validation_end = min(max(validation_end, train_end + 1), total - 1)
    elif total == 2:
        train_end, validation_end = 1, 1
    result = QuerySplits(seed, ids[:train_end], ids[train_end:validation_end], ids[validation_end:])
    result.validate_against(dataset)
    return result
