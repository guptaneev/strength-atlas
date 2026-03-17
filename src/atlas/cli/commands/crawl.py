import json

import typer
from sqlalchemy import select

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
