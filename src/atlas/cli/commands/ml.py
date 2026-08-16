"""Commands for preparing the immutable reranking experiment inputs."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import typer
import yaml

from atlas.db.engine import SessionLocal
from atlas.ml.baseline import evaluate_baseline
from atlas.ml.dataset import load_dataset, save_dataset
from atlas.ml.error_analysis import make_error_analysis_template, summarize_error_analysis
from atlas.ml.pools import build_candidate_pools
from atlas.ml.review import build_labeling_review
from atlas.ml.splits import split_queries
from atlas.ml.training import ExperimentTrackingConfig, bootstrap_label_dataset, train_cross_encoder
from atlas.ml.human_judgments import apply_human_judgments, load_human_judgments

app = typer.Typer(help="Prepare and evaluate the reranker experiment dataset.")


def _write_json(path: str, payload: object) -> None:
    Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


@app.command("build-pools")
def build_pools_cmd(
    dataset: str = typer.Option(..., "--dataset", help="Query dataset JSON (usually query-only)."),
    output: str = typer.Option(..., "--output", help="Draft candidate-pool JSON to review and label."),
    retrieval_depth: int = typer.Option(50, min=1),
    random_negatives: int = typer.Option(10, min=0),
    seed: int = typer.Option(42),
) -> None:
    data = load_dataset(dataset)
    with SessionLocal() as session:
        pooled = build_candidate_pools(session, data, retrieval_depth=retrieval_depth, random_negatives=random_negatives, seed=seed)
    save_dataset(pooled, output)
    typer.echo(f"Wrote {len(pooled.queries)} candidate pools to {output}; label every candidate before freezing.")


@app.command("export-review")
def export_review_cmd(
    dataset: str = typer.Option(..., "--dataset", help="Draft candidate-pool dataset JSON."),
    output: str = typer.Option(..., "--output", help="Portable JSON review sheet with program text."),
) -> None:
    data = load_dataset(dataset)
    with SessionLocal() as session:
        review = build_labeling_review(session, data)
    _write_json(output, review)
    typer.echo(f"Wrote review sheet for {len(data.queries)} query pools to {output}.")


@app.command("bootstrap-label")
def bootstrap_label_cmd(
    dataset: str = typer.Option(..., "--dataset", help="Draft candidate-pool JSON."),
    review: str = typer.Option(..., "--review", help="Review JSON containing candidate text."),
    output: str = typer.Option(..., "--output", help="Frozen teacher-distilled dataset JSON."),
    model: str = typer.Option("cross-encoder/ms-marco-MiniLM-L6-v2", "--model"),
    batch_size: int = typer.Option(16, min=1),
    max_length: int = typer.Option(256, min=32),
) -> None:
    data = load_dataset(dataset)
    review_data = json.loads(Path(review).read_text(encoding="utf-8"))
    labeled = bootstrap_label_dataset(data, review_data, model_name=model, batch_size=batch_size, max_length=max_length)
    save_dataset(labeled, output)
    typer.echo(f"Wrote {sum(len(q.candidates) for q in labeled.queries)} teacher-distilled judgments to {output}.")


@app.command("train")
def train_cmd(
    program_dataset: str = typer.Option(..., "--program-dataset"),
    program_review: str = typer.Option(..., "--program-review"),
    evidence_dataset: str = typer.Option(..., "--evidence-dataset"),
    evidence_review: str = typer.Option(..., "--evidence-review"),
    output_dir: str = typer.Option(..., "--output-dir"),
    config: str = typer.Option("configs/reranker-v1.yaml", "--config"),
    human_judgments: str | None = typer.Option(None, "--human-judgments", help="Optional authoritative program-grade overrides."),
    additional_program_dataset: str | None = typer.Option(None, "--additional-program-dataset", help="Frozen, fully judged program dataset to add to training."),
    additional_program_review: str | None = typer.Option(None, "--additional-program-review", help="Review export matching --additional-program-dataset."),
    fixed_evaluation_splits: str | None = typer.Option(None, "--fixed-evaluation-splits", help="JSON file with immutable validation and test query IDs."),
    wandb_project: str | None = typer.Option(None, "--wandb-project", envvar="WANDB_PROJECT", help="W&B project; required when tracking is enabled."),
    wandb_entity: str | None = typer.Option(None, "--wandb-entity", envvar="WANDB_ENTITY"),
    wandb_run_name: str | None = typer.Option(None, "--wandb-run-name"),
    wandb_mode: str = typer.Option("disabled", "--wandb-mode", envvar="WANDB_MODE", help="disabled, offline, or online."),
) -> None:
    values = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
    program_data = load_dataset(program_dataset, require_complete_judgments=True)
    human_labels = load_human_judgments(human_judgments) if human_judgments else {}
    if human_labels:
        program_data = apply_human_judgments(program_data, human_labels)
    inputs = [
        (program_data, json.loads(Path(program_review).read_text(encoding="utf-8"))),
        (load_dataset(evidence_dataset, require_complete_judgments=True), json.loads(Path(evidence_review).read_text(encoding="utf-8"))),
    ]
    authoritative = {
        (query_id, f"program:{program_id}")
        for (query_id, program_id) in human_labels
    }
    if bool(additional_program_dataset) != bool(additional_program_review):
        raise typer.BadParameter("--additional-program-dataset and --additional-program-review must be supplied together.")
    if additional_program_dataset and additional_program_review:
        additional_data = load_dataset(additional_program_dataset, require_complete_judgments=True)
        inputs.append((additional_data, json.loads(Path(additional_program_review).read_text(encoding="utf-8"))))
        authoritative.update(
            (query.query_id, f"program:{candidate.program_id}")
            for query in additional_data.queries
            for candidate in query.candidates
            if candidate.program_id is not None
        )
    fixed_splits = None
    if fixed_evaluation_splits:
        split_data = json.loads(Path(fixed_evaluation_splits).read_text(encoding="utf-8"))
        fixed_splits = {
            name: set(split_data.get(name, []))
            for name in ("validation", "test")
        }
    report = train_cross_encoder(
        inputs,
        model_name=values["model_checkpoint"],
        output_dir=output_dir,
        max_length=int(values["max_length"]),
        batch_size=int(values["batch_size"]),
        learning_rate=float(values["learning_rate"]),
        epochs=int(values["epochs"]),
        seed=int(values["seed"]),
        authoritative_keys=authoritative,
        fixed_evaluation_query_ids=fixed_splits,
        experiment_tracking=ExperimentTrackingConfig(
            project=wandb_project,
            entity=wandb_entity,
            run_name=wandb_run_name,
            mode=wandb_mode,
        ),
    )
    test = report["metrics"]["test"]
    typer.echo(f"Saved model to {output_dir}; test nDCG@10 {test['baseline_ndcg_at_10']:.4f} -> {test['reranker_ndcg_at_10']:.4f}.")


@app.command("apply-human-judgments")
def apply_human_judgments_cmd(
    dataset: str = typer.Option(..., "--dataset"),
    judgments: str = typer.Option(..., "--judgments"),
    output: str = typer.Option(..., "--output"),
    freeze: bool = typer.Option(False, "--freeze", help="Mark the result frozen after validating every candidate is judged."),
) -> None:
    data = load_dataset(dataset)
    updated = apply_human_judgments(data, load_human_judgments(judgments))
    if freeze:
        updated = replace(updated, status="frozen")
    save_dataset(updated, output)
    typer.echo(f"Wrote dataset with human-authoritative overrides to {output}.")


@app.command("split")
def split_cmd(
    dataset: str = typer.Option(..., "--dataset"),
    output: str = typer.Option(..., "--output"),
    seed: int = typer.Option(42),
) -> None:
    data = load_dataset(dataset)
    splits = split_queries(data, seed=seed)
    _write_json(output, {"dataset_version": data.version, "seed": splits.seed, "train_query_ids": splits.train_query_ids, "validation_query_ids": splits.validation_query_ids, "test_query_ids": splits.test_query_ids})
    typer.echo(f"Wrote query-level split to {output}")


@app.command("baseline")
def baseline_cmd(
    dataset: str = typer.Option(..., "--dataset", help="Fully judged, frozen dataset JSON."),
    output: str = typer.Option(..., "--output"),
    k: int = typer.Option(10, min=1),
    retrieval_depth: int = typer.Option(50, min=1),
) -> None:
    data = load_dataset(dataset, require_complete_judgments=True)
    if data.status != "frozen":
        raise typer.BadParameter("Baseline datasets must be marked status=frozen after human review.")
    with SessionLocal() as session:
        report = evaluate_baseline(session, data, k=k, retrieval_depth=retrieval_depth)
    _write_json(output, report)
    metrics = report["metrics"]
    typer.echo(f"nDCG@{k}={metrics['ndcg_at_k']:.4f} MRR={metrics['mrr']:.4f} Recall@{k}={metrics['recall_at_k']:.4f} Precision@{k}={metrics['precision_at_k']:.4f}")


@app.command("error-template")
def error_template_cmd(
    baseline_report: str = typer.Option(..., "--baseline-report"),
    output: str = typer.Option(..., "--output"),
) -> None:
    report = json.loads(Path(baseline_report).read_text(encoding="utf-8"))
    _write_json(output, make_error_analysis_template(report))
    typer.echo(f"Wrote manual error-analysis template to {output}")


@app.command("error-summary")
def error_summary_cmd(analysis: str = typer.Option(..., "--analysis"), json_output: bool = typer.Option(False, "--json")) -> None:
    summary = summarize_error_analysis(json.loads(Path(analysis).read_text(encoding="utf-8")))
    typer.echo(json.dumps(summary) if json_output else f"reviewed_queries={summary['reviewed_queries']} unreviewed_queries={summary['unreviewed_queries']}")
