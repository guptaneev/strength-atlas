import json
import datetime as dt

import typer
from sqlalchemy import select

from atlas.browser_use.client import BrowserUseClient
from atlas.db.engine import SessionLocal
from atlas.db.models import CrawlJob

app = typer.Typer(help="Crawl job inspection.")


@app.command("list")
def list_crawls(limit: int = 50, json_output: bool = typer.Option(False, "--json")) -> None:
    with SessionLocal() as session:
        rows = session.execute(select(CrawlJob).order_by(CrawlJob.started_at.desc()).limit(limit)).scalars().all()
        if json_output:
            data = [
                {
                    "id": row.id,
                    "job_type": row.job_type,
                    "source_id": row.source_id,
                    "target_url": row.target_url,
                    "status": row.status,
                    "retry_count": row.retry_count,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                }
                for row in rows
            ]
            typer.echo(json.dumps(data))
            return
        for row in rows:
            typer.echo(f"{row.id} {row.job_type} {row.status} {row.target_url}")


@app.command("stop")
def stop_crawl(
    crawl_id: int = typer.Option(..., "--crawl-id"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    with SessionLocal() as session:
        row = session.get(CrawlJob, crawl_id)
        if row is None:
            typer.echo(f"crawl not found: {crawl_id}")
            raise typer.Exit(code=1)

        if row.status not in ("pending", "running"):
            if json_output:
                typer.echo(
                    json.dumps(
                        {
                            "status": "no-op",
                            "crawl_id": crawl_id,
                            "crawl_status": row.status,
                        }
                    )
                )
            else:
                typer.echo(f"no-op: crawl_job_id={crawl_id} already status={row.status}")
            return

        browser_use_stopped = False
        browser_use_stop_error = None
        if row.browser_use_session_id:
            try:
                client = BrowserUseClient()
                run_async(client.stop_session(row.browser_use_session_id, strategy="task"))
                browser_use_stopped = True
            except Exception as exc:
                browser_use_stop_error = str(exc)

        row.status = "failed"
        row.completed_at = dt.datetime.now(dt.UTC)
        suffix = " (operator-stopped)"
        if row.error_message:
            if suffix not in row.error_message:
                row.error_message = f"{row.error_message}{suffix}"
        else:
            row.error_message = "Stopped by operator"
        session.commit()

        payload = {
            "status": "stopped",
            "crawl_id": crawl_id,
            "crawl_status": row.status,
            "browser_use_session_id": row.browser_use_session_id,
            "browser_use_stopped": browser_use_stopped,
            "browser_use_stop_error": browser_use_stop_error,
        }
        if json_output:
            typer.echo(json.dumps(payload))
            return
        typer.echo(
            " ".join(
                [
                    f"stopped crawl_job_id={crawl_id}",
                    f"browser_use_stopped={browser_use_stopped}",
                    f"error={browser_use_stop_error}" if browser_use_stop_error else "",
                ]
            ).strip()
        )


def run_async(coro):
    import asyncio

    return asyncio.run(coro)
