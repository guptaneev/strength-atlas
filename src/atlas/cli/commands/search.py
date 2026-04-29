import json

import typer

from atlas.db.engine import SessionLocal
from atlas.db.models import Document, Source
from atlas.search.evaluation import load_eval_suite, run_search_eval_suite
from atlas.search.programs import ProgramSearchFilters, search_programs
from atlas.search.sources import search_sources

app = typer.Typer(help="Search indexed content.")


@app.command("programs")
def search_programs_cmd(
    query: str = typer.Option("", "--query"),
    days_per_week: int | None = None,
    specialization: str | None = None,
    experience_level: str | None = None,
    progression_type: str | None = None,
    split_type: str | None = None,
    domain: str | None = None,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    filters = ProgramSearchFilters(
        days_per_week=days_per_week,
        specialization=specialization,
        experience_level=experience_level,
        progression_type=progression_type,
        split_type=split_type,
        domain=domain,
    )
    with SessionLocal() as session:
        rows = search_programs(session, query or None, filters)
        if json_output:
            data = []
            for row in rows:
                doc = session.get(Document, row.document_id)
                source = session.get(Source, doc.source_id) if doc else None
                data.append(
                    {
                        "id": row.id,
                        "name": row.name,
                        "confidence": row.confidence,
                        "document_id": row.document_id,
                        "source_id": doc.source_id if doc else None,
                        "canonical_url": source.canonical_url if source else None,
                    }
                )
            typer.echo(json.dumps(data))
            return
        for row in rows:
            typer.echo(f"{row.id} {row.name} conf={row.confidence}")


@app.command("sources")
def search_sources_cmd(
    query: str = typer.Option(..., "--query"),
    domain: str | None = typer.Option(None, "--domain"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    with SessionLocal() as session:
        rows = search_sources(session, query, domain=domain)
        if json_output:
            data = [
                {
                    "id": row.id,
                    "canonical_url": row.canonical_url,
                    "status": row.status,
                    "last_crawled_at": row.last_crawled_at.isoformat() if row.last_crawled_at else None,
                }
                for row in rows
            ]
            typer.echo(json.dumps(data))
            return
        for row in rows:
            typer.echo(f"{row.id} {row.canonical_url}")


@app.command("eval")
def eval_search_cmd(
    fixture: str = typer.Option(
        "docs/engineering/search-eval-fixture.json",
        "--fixture",
        help="Path to JSON eval suite.",
    ),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    suite = load_eval_suite(fixture)
    with SessionLocal() as session:
        summary = run_search_eval_suite(session, suite)
    if json_output:
        typer.echo(json.dumps(summary))
        return
    typer.echo(f"queries_total {summary['queries_total']}")
    typer.echo(f"queries_passed {summary['queries_passed']}")
    typer.echo(f"pass_rate {summary['pass_rate']:.3f}")
    for row in summary["results"]:
        status = "PASS" if row["passed"] else "FAIL"
        typer.echo(f"[{status}] {row['name']} mode={row['mode']} query={row['query']}")
        if row["missing_urls"]:
            typer.echo(f"missing_urls {', '.join(row['missing_urls'])}")
