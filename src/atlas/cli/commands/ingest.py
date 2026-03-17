from typing import List

import json

import typer
from sqlalchemy import select

from atlas.browser_use.client import BrowserUseClient
from atlas.db.engine import SessionLocal
from atlas.db.models import Source
from atlas.ingest.discovery import create_sources_from_urls, is_domain_allowlisted
from atlas.ingest.extraction import extract_url
from atlas.ingest.refresh import refresh_source

app = typer.Typer(help="Ingestion workflows.")


@app.command("discover")
def discover(
    domain: str,
    seed_url: List[str] = typer.Option(..., "--seed-url"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    with SessionLocal() as session:
        if not is_domain_allowlisted(session, domain):
            raise typer.Exit(code=1)
        # Placeholder until discovery is wired to Browser Use in the CLI.
        result = create_sources_from_urls(session, domain, seed_url)
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "created": len(result.created_sources),
                        "skipped": len(result.skipped_urls),
                    }
                )
            )
        else:
            typer.echo(f"created={len(result.created_sources)} skipped={len(result.skipped_urls)}")


@app.command("extract")
def extract(url: str, json_output: bool = typer.Option(False, "--json")) -> None:
    client = BrowserUseClient()
    with SessionLocal() as session:
        source = session.execute(select(Source).where(Source.url == url)).scalar_one_or_none()
        doc = run_async(extract_url(session, client, url, source))
        if json_output:
            typer.echo(json.dumps({"document_id": doc.id}))
        else:
            typer.echo(f"document_id={doc.id}")


@app.command("refresh")
def refresh(source_id: int, json_output: bool = typer.Option(False, "--json")) -> None:
    client = BrowserUseClient()
    with SessionLocal() as session:
        run_async(refresh_source(session, client, source_id))
        if json_output:
            typer.echo(json.dumps({"status": "refreshed", "source_id": source_id}))
        else:
            typer.echo("refreshed")


def run_async(coro):
    import asyncio
    return asyncio.run(coro)
