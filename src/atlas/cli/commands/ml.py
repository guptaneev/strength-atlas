"""Commands for preparing the immutable reranking experiment inputs."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from atlas.db.engine import SessionLocal
from atlas.ml.baseline import evaluate_baseline
from atlas.ml.dataset import load_dataset, save_dataset
from atlas.ml.error_analysis import make_error_analysis_template, summarize_error_analysis
from atlas.ml.pools import build_candidate_pools
from atlas.ml.splits import split_queries

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
