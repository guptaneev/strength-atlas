from typing import List

import json

import typer
from sqlalchemy import select

from atlas.browser_use.client import BrowserUseClient
from atlas.db.engine import SessionLocal
from atlas.db.models import Domain, Source
from atlas.ingest.concurrency import get_active_crawl_for_domain
from atlas.ingest.discovery import canonicalize_url
from atlas.ingest.discovery import discover_and_create_sources, is_domain_allowlisted
from atlas.ingest.extraction import extract_url
from atlas.ingest.refresh import refresh_source
from atlas.storage.client import SupabaseStorageClient

app = typer.Typer(help="Ingestion workflows.")


@app.command("discover")
def discover(
    domain: str = typer.Option(..., "--domain"),
    seed_url: List[str] = typer.Option(..., "--seed-url"),
    timeout_seconds: int | None = typer.Option(None, "--timeout-seconds"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    client = BrowserUseClient(poll_timeout_seconds=timeout_seconds)
    with SessionLocal() as session:
        if not is_domain_allowlisted(session, domain):
            raise typer.Exit(code=1)
        active = get_active_crawl_for_domain(session, domain)
        if active is not None:
            typer.echo(
                f"discover blocked: domain {domain} already has active crawl "
                f"(crawl_job_id={active.id}, status={active.status})"
            )
            raise typer.Exit(code=1)
        try:
            result = run_async(discover_and_create_sources(session, client, domain, seed_url))
        except TimeoutError as exc:
            typer.echo(f"discover timeout: {exc}")
            raise typer.Exit(code=1)
        except Exception as exc:
            typer.echo(f"discover failed: {exc}")
            raise typer.Exit(code=1)
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "created": len(result.created_sources),
                        "skipped": len(result.skipped_urls),
                        "candidates": len(result.candidate_urls or []),
                        "crawl_job_id": result.crawl_job.id if result.crawl_job else None,
                    }
                )
            )
        else:
            typer.echo(
                " ".join(
                    [
                        f"created={len(result.created_sources)}",
                        f"skipped={len(result.skipped_urls)}",
                        f"candidates={len(result.candidate_urls or [])}",
                        f"crawl_job_id={result.crawl_job.id if result.crawl_job else 'n/a'}",
                    ]
                )
            )


@app.command("extract")
def extract(
    url: str = typer.Option(..., "--url"),
    timeout_seconds: int | None = typer.Option(None, "--timeout-seconds"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    client = BrowserUseClient(poll_timeout_seconds=timeout_seconds)
    storage = SupabaseStorageClient()
    with SessionLocal() as session:
        canonical = canonicalize_url(url)
        source = session.execute(
            select(Source).where(Source.canonical_url == canonical)
        ).scalar_one_or_none()
        if source is None:
            typer.echo(
                f"extract failed: source not found for {canonical}. "
                "Run `atlas ingest discover` first for this domain."
            )
            raise typer.Exit(code=1)
        domain = session.execute(
            select(Domain.domain).join(Source, Source.domain_id == Domain.id).where(Source.id == source.id)
        ).scalar_one()
        active = get_active_crawl_for_domain(session, domain)
        if active is not None:
            typer.echo(
                f"extract blocked: domain {domain} already has active crawl "
                f"(crawl_job_id={active.id}, status={active.status})"
            )
            raise typer.Exit(code=1)
        try:
            doc = run_async(extract_url(session, client, url, source, storage=storage))
        except TimeoutError as exc:
            typer.echo(f"extract timeout: {exc}")
            raise typer.Exit(code=1)
        except Exception as exc:
            typer.echo(f"extract failed: {exc}")
            raise typer.Exit(code=1)
        if json_output:
            typer.echo(json.dumps({"document_id": doc.id}))
        else:
            typer.echo(f"document_id={doc.id}")


@app.command("refresh")
def refresh(
    source_id: int = typer.Option(..., "--source-id"),
    timeout_seconds: int | None = typer.Option(None, "--timeout-seconds"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    client = BrowserUseClient(poll_timeout_seconds=timeout_seconds)
    storage = SupabaseStorageClient()
    with SessionLocal() as session:
        source = session.get(Source, source_id)
        if source is None:
            typer.echo(f"refresh failed: source {source_id} not found")
            raise typer.Exit(code=1)
        domain = session.execute(select(Domain.domain).where(Domain.id == source.domain_id)).scalar_one()
        active = get_active_crawl_for_domain(session, domain)
        if active is not None:
            typer.echo(
                f"refresh blocked: domain {domain} already has active crawl "
                f"(crawl_job_id={active.id}, status={active.status})"
            )
            raise typer.Exit(code=1)
        try:
            run_async(refresh_source(session, client, source_id, storage=storage))
        except TimeoutError as exc:
            typer.echo(f"refresh timeout: {exc}")
            raise typer.Exit(code=1)
        except Exception as exc:
            typer.echo(f"refresh failed: {exc}")
            raise typer.Exit(code=1)
        if json_output:
            typer.echo(json.dumps({"status": "refreshed", "source_id": source_id}))
        else:
            typer.echo("refreshed")


def run_async(coro):
    import asyncio
    return asyncio.run(coro)
