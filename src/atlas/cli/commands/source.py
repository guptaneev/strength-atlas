import json

import typer
from sqlalchemy import select

from atlas.db.engine import SessionLocal
from atlas.db.models import Document, Program, Source

app = typer.Typer(help="Source inspection.")


@app.command("list")
def list_sources(limit: int = 50, json_output: bool = typer.Option(False, "--json")) -> None:
    with SessionLocal() as session:
        rows = session.execute(select(Source).limit(limit)).scalars().all()
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
            typer.echo(f"{row.id} {row.status} {row.canonical_url}")


@app.command("show")
def show_source(source_id: int, json_output: bool = typer.Option(False, "--json")) -> None:
    with SessionLocal() as session:
        source = session.get(Source, source_id)
        if not source:
            raise typer.Exit(code=1)
        doc = None
        programs = []
        if source.latest_document_id:
            doc = session.get(Document, source.latest_document_id)
            programs = session.execute(
                select(Program).where(Program.document_id == source.latest_document_id)
            ).scalars().all()
        if json_output:
            data = {
                "id": source.id,
                "canonical_url": source.canonical_url,
                "status": source.status,
                "last_crawled_at": source.last_crawled_at.isoformat() if source.last_crawled_at else None,
                "document": {
                    "id": doc.id,
                    "html_storage_path": doc.html_storage_path,
                    "extracted_json_storage_path": doc.extracted_json_storage_path,
                }
                if doc
                else None,
                "programs": [{"id": p.id, "name": p.name, "confidence": p.confidence} for p in programs],
            }
            typer.echo(json.dumps(data))
            return
        typer.echo(f"source {source.id} {source.canonical_url}")
        if doc:
            typer.echo(f"document {doc.id}")
            typer.echo(f"html {doc.html_storage_path}")
            typer.echo(f"extracted {doc.extracted_json_storage_path}")
        for program in programs:
            typer.echo(f"program {program.id} {program.name} conf={program.confidence}")
