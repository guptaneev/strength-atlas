from typing import List

import json

import typer
from sqlalchemy import exists, select

from atlas.browser_use.client import BrowserUseClient
from atlas.db.engine import SessionLocal
from atlas.db.models import CrawlJob, Document, Domain, Program, Source
from atlas.ingest.concurrency import get_active_crawl_for_domain
from atlas.ingest.discovery import canonicalize_url
from atlas.ingest.discovery import discover_and_create_sources, is_domain_allowlisted
from atlas.ingest.extraction import build_extraction_diagnostics, extract_url
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
        client = BrowserUseClient(poll_timeout_seconds=timeout_seconds)
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
        client = BrowserUseClient(poll_timeout_seconds=timeout_seconds)
        storage = SupabaseStorageClient()
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
        client = BrowserUseClient(poll_timeout_seconds=timeout_seconds)
        storage = SupabaseStorageClient()
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


@app.command("diagnose")
def diagnose(
    source_id: int | None = typer.Option(None, "--source-id"),
    crawl_id: int | None = typer.Option(None, "--crawl-id"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    if source_id is None and crawl_id is None:
        typer.echo("diagnose failed: provide --source-id or --crawl-id")
        raise typer.Exit(code=1)

    storage = SupabaseStorageClient()
    with SessionLocal() as session:
        source = session.get(Source, source_id) if source_id else None
        crawl = session.get(CrawlJob, crawl_id) if crawl_id else None
        document = None
        if crawl is not None:
            document = session.execute(select(Document).where(Document.crawl_job_id == crawl.id)).scalar_one_or_none()
            if source is None and crawl.source_id is not None:
                source = session.get(Source, crawl.source_id)
        elif source is not None and source.latest_document_id:
            document = session.get(Document, source.latest_document_id)
            if document and document.crawl_job_id:
                crawl = session.get(CrawlJob, document.crawl_job_id)

        if source is None:
            typer.echo("diagnose failed: source not found")
            raise typer.Exit(code=1)
        if document is None:
            typer.echo("diagnose failed: no document available")
            raise typer.Exit(code=1)

        payload = None
        if document.extracted_json_storage_path:
            try:
                payload = storage.download_json_or_text(document.extracted_json_storage_path)
            except Exception as exc:
                payload = f"artifact_read_error: {exc}"

        diagnostics = build_extraction_diagnostics(payload, url=source.url)
        programs_in_db = session.execute(
            select(Program).where(Program.document_id == document.id)
        ).scalars().all()

        result = {
            "source_id": source.id,
            "canonical_url": source.canonical_url,
            "document_id": document.id,
            "crawl_id": crawl.id if crawl else None,
            "crawl_status": crawl.status if crawl else None,
            "artifact_path": document.extracted_json_storage_path,
            "payload_type": diagnostics["payload_type"],
            "parse_confidence": diagnostics["parse_confidence"],
            "raw_text_length": diagnostics["raw_text_length"],
            "programs_in_payload": diagnostics["programs_count"],
            "programs_in_db": len(programs_in_db),
            "validation_errors": diagnostics["validation_errors"],
            "warnings": diagnostics["warnings"],
        }
        if json_output:
            typer.echo(json.dumps(result))
            return
        typer.echo(f"source_id {result['source_id']}")
        typer.echo(f"url {result['canonical_url']}")
        typer.echo(f"document_id {result['document_id']}")
        typer.echo(f"crawl_id {result['crawl_id']}")
        typer.echo(f"crawl_status {result['crawl_status'] or 'n/a'}")
        typer.echo(f"artifact {result['artifact_path'] or 'n/a'}")
        typer.echo(f"payload_type {result['payload_type']}")
        typer.echo(f"parse_confidence {result['parse_confidence']}")
        typer.echo(f"raw_text_length {result['raw_text_length']}")
        typer.echo(f"programs_in_payload {result['programs_in_payload']}")
        typer.echo(f"programs_in_db {result['programs_in_db']}")
        typer.echo(f"validation_errors {', '.join(result['validation_errors']) if result['validation_errors'] else 'none'}")
        typer.echo(f"warnings {', '.join(result['warnings']) if result['warnings'] else 'none'}")


@app.command("reextract-empty")
def reextract_empty(
    domain: str = typer.Option(..., "--domain"),
    limit: int = typer.Option(25, "--limit"),
    timeout_seconds: int | None = typer.Option(None, "--timeout-seconds"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    import asyncio

    with SessionLocal() as session:
        active = get_active_crawl_for_domain(session, domain)
        if active is not None:
            typer.echo(
                f"reextract blocked: domain {domain} already has active crawl "
                f"(crawl_job_id={active.id}, status={active.status})"
            )
            raise typer.Exit(code=1)

        missing_program_sources = _sources_with_empty_programs(session, domain=domain, limit=limit)
        if not missing_program_sources:
            if json_output:
                typer.echo(json.dumps({"queued": 0, "processed": 0, "succeeded": 0, "failed": 0, "results": []}))
            else:
                typer.echo("no sources with empty programs")
            return
        client = BrowserUseClient(poll_timeout_seconds=timeout_seconds)
        storage = SupabaseStorageClient()
        runner = asyncio.Runner()

        results: list[dict[str, object]] = []
        try:
            for src in missing_program_sources:
                try:
                    doc = runner.run(extract_url(session, client, src.url, src, storage=storage))
                    results.append(
                        {"source_id": src.id, "status": "succeeded", "document_id": doc.id, "error": None}
                    )
                except Exception as exc:
                    results.append(
                        {"source_id": src.id, "status": "failed", "document_id": None, "error": str(exc)}
                    )
        finally:
            try:
                runner.run(client.close())
            except Exception:
                pass
            runner.close()

        succeeded = len([r for r in results if r["status"] == "succeeded"])
        failed = len(results) - succeeded
        payload = {
            "queued": len(missing_program_sources),
            "processed": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }
        if json_output:
            typer.echo(json.dumps(payload))
        else:
            typer.echo(
                f"queued={payload['queued']} processed={payload['processed']} "
                f"succeeded={payload['succeeded']} failed={payload['failed']}"
            )


def _sources_with_empty_programs(session, *, domain: str, limit: int) -> list[Source]:
    no_programs = ~exists(select(Program.id).where(Program.document_id == Source.latest_document_id))
    stmt = (
        select(Source)
        .join(Domain, Domain.id == Source.domain_id)
        .where(
            Domain.domain == domain,
            Source.status == "succeeded",
            Source.latest_document_id.is_not(None),
            no_programs,
        )
        .order_by(Source.id.asc())
        .limit(limit)
    )
    return session.execute(stmt).scalars().all()


def run_async(coro):
    import asyncio
    return asyncio.run(coro)
