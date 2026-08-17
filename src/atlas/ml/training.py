"""Reproducible cross-encoder bootstrap training and ranking evaluation."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import random
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from atlas.ml.dataset import CandidateJudgment, RelevanceDataset, RelevanceQuery, save_dataset
from atlas.search.metrics import evaluate_ranking


@dataclass(frozen=True)
class TrainingPair:
    query_id: str
    query: str
    candidate_key: str
    candidate_text: str
    relevance: int
    baseline_rank: int | None


@dataclass(frozen=True)
class ExperimentTrackingConfig:
    """Optional Weights & Biases settings for a single training run."""

    project: str | None = None
    entity: str | None = None
    run_name: str | None = None
    mode: str = "disabled"


def _start_wandb_run(config: ExperimentTrackingConfig, run_config: dict[str, Any]):
    """Start an opt-in W&B run without making model serving depend on W&B."""
    if config.mode == "disabled":
        return None
    if config.mode not in {"online", "offline"}:
        raise ValueError("wandb_mode must be one of: disabled, offline, online")
    if not config.project:
        raise ValueError("wandb_project is required when W&B tracking is enabled")
    try:
        import wandb
    except ImportError as exc:
        raise RuntimeError('Install the experiment extra with: pip install -e ".[experiment]"') from exc
    return wandb.init(
        project=config.project,
        entity=config.entity,
        name=config.run_name,
        mode=config.mode,
        job_type="reranker-training",
        tags=["reranker", "cross-encoder"],
        config=run_config,
    )


def _log_wandb_report_artifact(run: Any, report_path: Path) -> None:
    """Upload only the reproducibility report, never the corpus or model weights."""
    import wandb

    artifact = wandb.Artifact("reranker-training-report", type="reranker-evaluation")
    artifact.add_file(str(report_path), name="training-report.json")
    run.log_artifact(artifact)


class _PairDataset(Dataset):
    def __init__(self, pairs: list[TrainingPair]) -> None:
        self.pairs = pairs

    def __len__(self) -> int:
        return len(self.pairs)

    def __getitem__(self, index: int) -> TrainingPair:
        return self.pairs[index]


def bootstrap_label_dataset(
    dataset: RelevanceDataset,
    review: dict[str, Any],
    *,
    model_name: str,
    batch_size: int,
    max_length: int,
) -> RelevanceDataset:
    """Create teacher-distilled grades for an initial reproducible benchmark.

    These labels are useful for engineering and model bootstrapping, but are
    deliberately not represented as human relevance judgments.
    """
    text_map = _review_text_map(review)
    scorer = TransformerScorer(model_name, max_length=max_length)
    labeled_queries: list[RelevanceQuery] = []
    for query in dataset.queries:
        texts = [text_map[(query.query_id, candidate.key)] for candidate in query.candidates]
        scores = scorer.score(query.query, texts, batch_size=batch_size)
        rank_by_index = {index: rank for rank, index in enumerate(sorted(range(len(scores)), key=scores.__getitem__, reverse=True), start=1)}
        candidates = [
            replace(candidate, relevance=_grade_for_rank(rank_by_index[index], len(scores)), reason="teacher_distilled_v1")
            for index, candidate in enumerate(query.candidates)
        ]
        labeled_queries.append(replace(query, candidates=candidates))
    return RelevanceDataset(dataset.version, "frozen", dataset.document_representation, labeled_queries)


def train_cross_encoder(
    datasets_and_reviews: list[tuple[RelevanceDataset, dict[str, Any]]],
    *,
    model_name: str,
    output_dir: str | Path,
    max_length: int = 256,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
    epochs: int = 2,
    seed: int = 42,
    authoritative_keys: set[tuple[str, str]] | None = None,
    experiment_tracking: ExperimentTrackingConfig | None = None,
    fixed_evaluation_query_ids: dict[str, set[str]] | None = None,
    bootstrap_iterations: int = 1000,
) -> dict[str, Any]:
    """Fine-tune one regression cross-encoder across all candidate collections."""
    random.seed(seed)
    torch.manual_seed(seed)
    pairs = _all_pairs(datasets_and_reviews)
    query_ids = sorted({pair.query_id for pair in pairs})
    random.Random(seed).shuffle(query_ids)
    authoritative_keys = authoritative_keys or set()
    authoritative_query_ids = {query_id for query_id, _candidate_key in authoritative_keys}
    split_ids = _split_query_ids(
        query_ids,
        seed=seed,
        authoritative_query_ids=authoritative_query_ids,
        fixed_evaluation_query_ids=fixed_evaluation_query_ids,
    )
    split_pairs = {name: [pair for pair in pairs if pair.query_id in ids] for name, ids in split_ids.items()}
    # Human grades express the product owner's exact preference. Repeating them
    # gives those scarce labels a materially stronger training signal than
    # bootstrap-only examples without modifying their recorded source.
    original_train_pairs = list(split_pairs["train"])
    split_pairs["train"].extend(
        pair for pair in original_train_pairs for _ in range(4)
        if (pair.query_id, pair.candidate_key) in authoritative_keys
    )

    tracking = experiment_tracking or ExperimentTrackingConfig()
    run = _start_wandb_run(
        tracking,
        {
            "base_checkpoint": model_name,
            "max_length": max_length,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "epochs": epochs,
            "seed": seed,
            "authoritative_human_judgments": len(authoritative_keys),
            "query_counts": {name: len(ids) for name, ids in split_ids.items()},
            "pair_counts": {name: len(values) for name, values in split_pairs.items()},
        },
    )

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=1)
        model.train()
        optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
        losses: list[float] = []

        def collate(batch: list[TrainingPair]):
            encoded = tokenizer(
                [item.query for item in batch],
                [item.candidate_text for item in batch],
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            labels = torch.tensor([item.relevance / 3.0 for item in batch], dtype=torch.float32)
            return encoded, labels

        generator = torch.Generator().manual_seed(seed)
        loader = DataLoader(_PairDataset(split_pairs["train"]), batch_size=batch_size, shuffle=True, collate_fn=collate, generator=generator)
        for epoch in range(epochs):
            epoch_losses: list[float] = []
            for encoded, labels in loader:
                optimizer.zero_grad(set_to_none=True)
                scores = model(**encoded).logits.squeeze(-1)
                loss = torch.nn.functional.mse_loss(scores, labels)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                loss_value = float(loss.detach())
                losses.append(loss_value)
                epoch_losses.append(loss_value)
            if run is not None:
                run.log({"train/epoch": epoch + 1, "train/loss": fmean(epoch_losses) if epoch_losses else None})

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(output_path)
        tokenizer.save_pretrained(output_path)

        model.eval()
        metrics = {
            split: _evaluate_pairs(
                model,
                tokenizer,
                split_pairs[split],
                max_length=max_length,
                batch_size=batch_size,
                bootstrap_iterations=bootstrap_iterations,
                bootstrap_seed=seed,
            )
            for split in ("validation", "test")
        }
        report = {
            "model": "strength-atlas-cross-encoder-v1",
            "base_checkpoint": model_name,
            "supervision": "teacher_distilled_v1",
            "authoritative_human_judgments": len(authoritative_keys),
            "warning": "Bootstrap labels are model-distilled; only recorded human overrides are authoritative.",
            "seed": seed,
            "max_length": max_length,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "epochs": epochs,
            "bootstrap_iterations": bootstrap_iterations,
            "query_splits": {name: sorted(ids) for name, ids in split_ids.items()},
            "pair_counts": {name: len(values) for name, values in split_pairs.items()},
            "mean_training_loss": fmean(losses) if losses else None,
            "metrics": metrics,
        }
        report_path = output_path / "training-report.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if run is not None:
            metric_summary = {
                f"{split}/{metric_name}": metric_value
                for split, split_metrics in metrics.items()
                for metric_name, metric_value in split_metrics.items()
                if isinstance(metric_value, (int, float))
            }
            run.log({"train/mean_loss": report["mean_training_loss"], **metric_summary})
            _log_wandb_report_artifact(run, report_path)
        return report
    finally:
        if run is not None:
            run.finish()


class TransformerScorer:
    def __init__(self, model_name_or_path: str, *, max_length: int = 256) -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name_or_path)
        self.model.eval()
        self.max_length = max_length

    def score(self, query: str, texts: list[str], *, batch_size: int = 16) -> list[float]:
        scores: list[float] = []
        with torch.inference_mode():
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                encoded = self.tokenizer([query] * len(batch), batch, padding=True, truncation=True, max_length=self.max_length, return_tensors="pt")
                scores.extend(self.model(**encoded).logits.squeeze(-1).tolist())
        return [float(score) for score in scores]


def _review_text_map(review: dict[str, Any]) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    registry = review.get("candidate_documents", {})
    for query in review["queries"]:
        for candidate in query["candidates"]:
            key = f"program:{candidate['program_id']}" if candidate.get("program_id") is not None else f"source:{candidate['source_id']}"
            document = registry.get(key, {})
            text = candidate.get("program_text") or candidate.get("evidence_text") or document.get("program_text") or document.get("evidence_text")
            if not text:
                raise ValueError(f"Missing candidate text for {query['query_id']} {key}")
            result[(query["query_id"], key)] = text
    return result


def _all_pairs(datasets_and_reviews: Iterable[tuple[RelevanceDataset, dict[str, Any]]]) -> list[TrainingPair]:
    result: list[TrainingPair] = []
    for dataset, review in datasets_and_reviews:
        dataset.validate(require_complete_judgments=True)
        text_map = _review_text_map(review)
        for query in dataset.queries:
            for candidate in query.candidates:
                result.append(TrainingPair(query.query_id, query.query, candidate.key, text_map[(query.query_id, candidate.key)], candidate.relevance or 0, candidate.baseline_rank))
    return result


def _split_query_ids(
    query_ids: list[str],
    *,
    seed: int,
    authoritative_query_ids: set[str],
    fixed_evaluation_query_ids: dict[str, set[str]] | None,
) -> dict[str, set[str]]:
    """Make a train/validation/test partition without leaking reviewed data."""
    all_ids = set(query_ids)
    if fixed_evaluation_query_ids is not None:
        validation_ids = set(fixed_evaluation_query_ids.get("validation", set()))
        test_ids = set(fixed_evaluation_query_ids.get("test", set()))
        if validation_ids & test_ids:
            raise ValueError("Fixed validation and test query IDs must not overlap")
        unknown = (validation_ids | test_ids) - all_ids
        if unknown:
            raise ValueError(f"Fixed evaluation query IDs are absent from the dataset: {sorted(unknown)}")
        leaked = authoritative_query_ids & (validation_ids | test_ids)
        if leaked:
            raise ValueError(f"Authoritative training labels overlap fixed evaluation queries: {sorted(leaked)}")
        return {
            "train": all_ids - validation_ids - test_ids,
            "validation": validation_ids,
            "test": test_ids,
        }

    shuffled_ids = list(query_ids)
    random.Random(seed).shuffle(shuffled_ids)
    train_end = max(1, round(len(shuffled_ids) * 0.70))
    validation_end = max(train_end + 1, train_end + round(len(shuffled_ids) * 0.15))
    validation_end = min(validation_end, len(shuffled_ids) - 1)
    train_ids = set(shuffled_ids[:train_end]) | authoritative_query_ids
    remaining_ids = [query_id for query_id in shuffled_ids if query_id not in train_ids]
    validation_size = min(len(remaining_ids) - 1, max(1, validation_end - train_end)) if len(remaining_ids) >= 2 else 0
    return {
        "train": train_ids,
        "validation": set(remaining_ids[:validation_size]),
        "test": set(remaining_ids[validation_size:]),
    }


def _grade_for_rank(rank: int, size: int) -> int:
    if rank <= min(2, size):
        return 3
    if rank <= min(5, size):
        return 2
    if rank <= min(10, size):
        return 1
    return 0


def _evaluate_pairs(
    model,
    tokenizer,
    pairs: list[TrainingPair],
    *,
    max_length: int,
    batch_size: int,
    bootstrap_iterations: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    grouped: dict[str, list[TrainingPair]] = {}
    for pair in pairs:
        grouped.setdefault(pair.query_id, []).append(pair)
    baseline_rows = []
    model_rows = []
    per_query_metrics: list[dict[str, float | str]] = []
    scorer = _LoadedScorer(model, tokenizer, max_length)
    for query_id, query_pairs in grouped.items():
        baseline = sorted(query_pairs, key=lambda pair: pair.baseline_rank if pair.baseline_rank is not None else 10**9)
        scores = scorer.score(query_pairs[0].query, [pair.candidate_text for pair in query_pairs], batch_size=batch_size)
        reranked = [pair for _, pair in sorted(zip(scores, query_pairs, strict=True), key=lambda item: item[0], reverse=True)]
        total_relevant = sum(pair.relevance > 0 for pair in query_pairs)
        baseline_rows.append(evaluate_ranking([pair.relevance for pair in baseline], total_relevant=total_relevant, k=10))
        model_rows.append(evaluate_ranking([pair.relevance for pair in reranked], total_relevant=total_relevant, k=10))
        per_query_metrics.append(
            {
                "query_id": query_id,
                "baseline_ndcg_at_10": baseline_rows[-1].ndcg,
                "reranker_ndcg_at_10": model_rows[-1].ndcg,
                "baseline_mrr": baseline_rows[-1].reciprocal_rank,
                "reranker_mrr": model_rows[-1].reciprocal_rank,
            }
        )
    baseline_ndcg_values = [row.ndcg for row in baseline_rows]
    reranker_ndcg_values = [row.ndcg for row in model_rows]
    return {
        "queries": float(len(grouped)),
        "baseline_ndcg_at_10": fmean(baseline_ndcg_values) if baseline_rows else 0.0,
        "reranker_ndcg_at_10": fmean(reranker_ndcg_values) if model_rows else 0.0,
        "ndcg_at_10_delta": (fmean(reranker_ndcg_values) - fmean(baseline_ndcg_values)) if baseline_rows else 0.0,
        "baseline_mrr": fmean(row.reciprocal_rank for row in baseline_rows) if baseline_rows else 0.0,
        "reranker_mrr": fmean(row.reciprocal_rank for row in model_rows) if model_rows else 0.0,
        "baseline_ndcg_at_10_bootstrap_95_ci": bootstrap_mean_confidence_interval(
            baseline_ndcg_values,
            iterations=bootstrap_iterations,
            seed=bootstrap_seed,
        ),
        "reranker_ndcg_at_10_bootstrap_95_ci": bootstrap_mean_confidence_interval(
            reranker_ndcg_values,
            iterations=bootstrap_iterations,
            seed=bootstrap_seed,
        ),
        "per_query_metrics": per_query_metrics,
    }


def bootstrap_mean_confidence_interval(
    values: list[float],
    *,
    iterations: int = 1000,
    seed: int = 42,
) -> dict[str, float | int]:
    """Query-level nonparametric bootstrap interval for a mean metric."""
    if not values:
        return {"lower": 0.0, "upper": 0.0, "iterations": iterations}
    if iterations < 1:
        raise ValueError("bootstrap_iterations must be at least 1")
    rng = random.Random(seed)
    sample_size = len(values)
    means = sorted(fmean(rng.choice(values) for _ in range(sample_size)) for _ in range(iterations))
    lower_index = max(0, round((iterations - 1) * 0.025))
    upper_index = min(iterations - 1, round((iterations - 1) * 0.975))
    return {"lower": means[lower_index], "upper": means[upper_index], "iterations": iterations}


class _LoadedScorer:
    def __init__(self, model, tokenizer, max_length: int) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.max_length = max_length

    def score(self, query: str, texts: list[str], *, batch_size: int) -> list[float]:
        scores: list[float] = []
        with torch.inference_mode():
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                encoded = self.tokenizer([query] * len(batch), batch, padding=True, truncation=True, max_length=self.max_length, return_tensors="pt")
                scores.extend(float(value) for value in self.model(**encoded).logits.squeeze(-1).tolist())
        return scores


def save_bootstrap_dataset(dataset: RelevanceDataset, path: str | Path) -> None:
    save_dataset(dataset, path)
