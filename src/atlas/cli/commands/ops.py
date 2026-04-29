from __future__ import annotations

import json
from typing import List

import typer

from atlas.config.settings import get_settings
from atlas.ops.ledger import read_recent_run_records
from atlas.ops.metrics import summarize_run_history
from atlas.ops.policies import should_fail_run
from atlas.ops.runner import OpsRunOptions, run_ops_cycle

app = typer.Typer(help="Automated ingest operations and metrics.")


@app.command("run")
def run_ops(
    domain: List[str] = typer.Option([], "--domain", help="Repeatable domain filter. Defaults to all allowlisted/non-paused."),
    per_domain_limit: int | None = typer.Option(None, "--per-domain-limit"),
    global_limit: int | None = typer.Option(None, "--global-limit"),
    timeout_seconds: int | None = typer.Option(None, "--timeout-seconds"),
    discover_first: bool = typer.Option(False, "--discover-first"),
    discover_seed_url: List[str] = typer.Option(
        [],
        "--discover-seed-url",
        help="Repeatable seed URL. Use 'domain=url' for domain-specific seeds, or plain URL for all selected domains.",
    ),
    domain_policy_file: str | None = typer.Option(
        None,
        "--domain-policy-file",
        help="Optional JSON file with per-domain seed URLs and limits.",
    ),
    ledger_path: str | None = typer.Option(None, "--ledger-path"),
    failure_rate_threshold: float | None = typer.Option(None, "--failure-rate-threshold"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    settings = get_settings()
    resolved_per_domain_limit = per_domain_limit if per_domain_limit is not None else settings.ops_per_domain_limit
    resolved_global_limit = global_limit if global_limit is not None else settings.ops_global_limit
    resolved_timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.browser_use_poll_timeout_seconds
    resolved_ledger_path = ledger_path if ledger_path is not None else settings.ops_runs_ledger_path
    resolved_failure_threshold = (
        failure_rate_threshold
        if failure_rate_threshold is not None
        else settings.ops_failure_rate_threshold
    )

    summary = run_ops_cycle(
        OpsRunOptions(
            domains=domain or None,
            per_domain_limit=resolved_per_domain_limit,
            global_limit=resolved_global_limit,
            timeout_seconds=resolved_timeout_seconds,
            discover_first=discover_first,
            discover_seed_urls=discover_seed_url,
            failure_rate_threshold=resolved_failure_threshold,
            ledger_path=resolved_ledger_path,
            domain_policy_file=domain_policy_file,
            dry_run=False,
            persist_ledger=True,
        )
    )

    if json_output:
        typer.echo(json.dumps(summary))
    else:
        _print_run_summary(summary)

    if should_fail_run(summary, resolved_failure_threshold):
        raise typer.Exit(code=2)


@app.command("dry-run")
def dry_run_ops(
    domain: List[str] = typer.Option([], "--domain", help="Repeatable domain filter. Defaults to all allowlisted/non-paused."),
    per_domain_limit: int | None = typer.Option(None, "--per-domain-limit"),
    global_limit: int | None = typer.Option(None, "--global-limit"),
    discover_first: bool = typer.Option(False, "--discover-first"),
    discover_seed_url: List[str] = typer.Option(
        [],
        "--discover-seed-url",
        help="Repeatable seed URL. Use 'domain=url' for domain-specific seeds, or plain URL for all selected domains.",
    ),
    domain_policy_file: str | None = typer.Option(
        None,
        "--domain-policy-file",
        help="Optional JSON file with per-domain seed URLs and limits.",
    ),
    ledger_path: str | None = typer.Option(None, "--ledger-path"),
    failure_rate_threshold: float | None = typer.Option(None, "--failure-rate-threshold"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    settings = get_settings()
    resolved_per_domain_limit = per_domain_limit if per_domain_limit is not None else settings.ops_per_domain_limit
    resolved_global_limit = global_limit if global_limit is not None else settings.ops_global_limit
    resolved_ledger_path = ledger_path if ledger_path is not None else settings.ops_runs_ledger_path
    resolved_failure_threshold = (
        failure_rate_threshold
        if failure_rate_threshold is not None
        else settings.ops_failure_rate_threshold
    )

    summary = run_ops_cycle(
        OpsRunOptions(
            domains=domain or None,
            per_domain_limit=resolved_per_domain_limit,
            global_limit=resolved_global_limit,
            timeout_seconds=None,
            discover_first=discover_first,
            discover_seed_urls=discover_seed_url,
            failure_rate_threshold=resolved_failure_threshold,
            ledger_path=resolved_ledger_path,
            domain_policy_file=domain_policy_file,
            dry_run=True,
            persist_ledger=False,
        )
    )

    if json_output:
        typer.echo(json.dumps(summary))
    else:
        _print_run_summary(summary)


@app.command("metrics")
def show_ops_metrics(
    limit: int = typer.Option(20, "--limit"),
    ledger_path: str | None = typer.Option(None, "--ledger-path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    settings = get_settings()
    resolved_ledger_path = ledger_path if ledger_path is not None else settings.ops_runs_ledger_path

    runs = read_recent_run_records(resolved_ledger_path, limit=limit)
    summary = summarize_run_history(runs)

    if json_output:
        typer.echo(json.dumps(summary))
        return

    typer.echo(f"runs_analyzed {summary['runs_analyzed']}")
    typer.echo(f"latest_run_id {summary['latest_run_id'] or 'n/a'}")
    typer.echo(f"latest_completed_at {summary['latest_completed_at'] or 'n/a'}")
    totals = summary["totals"]
    typer.echo(
        " ".join(
            [
                f"processed={totals['processed']}",
                f"succeeded={totals['succeeded']}",
                f"failed={totals['failed']}",
                f"blocked={totals['blocked']}",
                f"blocked_domain_gates={totals.get('blocked_domain_gates', 0)}",
                f"skipped={totals['skipped']}",
                f"cost_usd={totals['browser_use_cost_usd_total']:.5f}",
                f"duration_seconds={totals['duration_seconds_total']:.2f}",
            ]
        )
    )
    typer.echo(f"avg_failure_rate {summary['avg_failure_rate']:.3f}")
    typer.echo(f"max_failure_rate {summary['max_failure_rate']:.3f}")
    for err in summary["top_error_codes"]:
        typer.echo(f"error {err['code']} count={err['count']}")


def _print_run_summary(summary: dict) -> None:
    totals = summary["totals"]
    typer.echo(f"run_id {summary['run_id']}")
    typer.echo(f"started_at {summary['started_at']}")
    typer.echo(f"completed_at {summary['completed_at']}")
    typer.echo(
        " ".join(
            [
                f"domains_scanned={totals['domains_scanned']}",
                f"sources_queued={totals['sources_queued']}",
                f"processed={totals['processed']}",
                f"succeeded={totals['succeeded']}",
                f"failed={totals['failed']}",
                f"blocked={totals['blocked']}",
                f"blocked_domain_gates={totals.get('blocked_domain_gates', 0)}",
                f"skipped={totals['skipped']}",
            ]
        )
    )
    typer.echo(
        " ".join(
            [
                f"programs_created_total={totals['programs_created_total']}",
                f"program_yield_rate={totals['program_yield_rate']:.3f}",
                f"avg_parse_confidence={totals['avg_parse_confidence'] if totals['avg_parse_confidence'] is not None else 'n/a'}",
                f"empty_program_successes={totals['empty_program_successes']}",
            ]
        )
    )
    typer.echo(
        " ".join(
            [
                f"failure_rate={totals['failure_rate']:.3f}",
                f"retry_events={totals['retry_events']}",
                f"timeout_count={totals['timeout_count']}",
                f"cost_usd={totals['browser_use_cost_usd_total']:.5f}",
                f"duration_seconds={totals['duration_seconds']:.2f}",
                f"avg_cost_per_success={totals['avg_cost_per_success'] if totals['avg_cost_per_success'] is not None else 'n/a'}",
            ]
        )
    )
    for err in totals["top_error_codes"]:
        typer.echo(f"error {err['code']} count={err['count']}")
