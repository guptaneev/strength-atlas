import json

import typer
from sqlalchemy import select

from atlas.db.engine import SessionLocal
from atlas.db.models import Domain

app = typer.Typer(help="Manage allowlisted domains.")


@app.command("add")
def add_domain(
    domain: str,
    allowlisted: bool = True,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    with SessionLocal() as session:
        existing = session.execute(select(Domain).where(Domain.domain == domain)).scalar_one_or_none()
        if existing:
            existing.allowlisted = allowlisted
            session.commit()
            if json_output:
                typer.echo(json.dumps({"status": "updated", "domain": domain, "allowlisted": allowlisted}))
            else:
                typer.echo(f"updated {domain}")
            return
        session.add(Domain(domain=domain, allowlisted=allowlisted))
        session.commit()
        if json_output:
            typer.echo(json.dumps({"status": "added", "domain": domain, "allowlisted": allowlisted}))
        else:
            typer.echo(f"added {domain}")


@app.command("list")
def list_domains(json_output: bool = typer.Option(False, "--json")) -> None:
    with SessionLocal() as session:
        rows = session.execute(select(Domain)).scalars().all()
        if json_output:
            data = [
                {"domain": row.domain, "allowlisted": row.allowlisted, "paused": row.paused}
                for row in rows
            ]
            typer.echo(json.dumps(data))
            return
        for row in rows:
            typer.echo(f"{row.domain} allowlisted={row.allowlisted} paused={row.paused}")


@app.command("pause")
def pause_domain(domain: str, json_output: bool = typer.Option(False, "--json")) -> None:
    with SessionLocal() as session:
        row = session.execute(select(Domain).where(Domain.domain == domain)).scalar_one_or_none()
        if not row:
            raise typer.Exit(code=1)
        row.paused = True
        session.commit()
        if json_output:
            typer.echo(json.dumps({"status": "paused", "domain": domain}))
        else:
            typer.echo(f"paused {domain}")


@app.command("resume")
def resume_domain(domain: str, json_output: bool = typer.Option(False, "--json")) -> None:
    with SessionLocal() as session:
        row = session.execute(select(Domain).where(Domain.domain == domain)).scalar_one_or_none()
        if not row:
            raise typer.Exit(code=1)
        row.paused = False
        session.commit()
        if json_output:
            typer.echo(json.dumps({"status": "resumed", "domain": domain}))
        else:
            typer.echo(f"resumed {domain}")
