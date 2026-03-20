import json

import typer

from atlas.db.engine import SessionLocal
from atlas.db.models import Document, Source
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
