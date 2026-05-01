from __future__ import annotations

import json

from typer.testing import CliRunner

from atlas.cli.app import app


def _run_summary(*, failure_rate: float = 0.0, failed: int = 0) -> dict:
    return {
        "run_id": "run-1",
        "started_at": "2026-01-01T00:00:00+00:00",
        "completed_at": "2026-01-01T00:01:00+00:00",
        "policy": {"failure_rate_threshold": 0.35},
        "totals": {
            "domains_scanned": 1,
            "sources_queued": 1,
            "processed": 1 + failed,
            "succeeded": 1,
            "failed": failed,
            "blocked": 0,
            "skipped": 0,
            "programs_created_total": 1,
            "program_yield_rate": 1.0,
            "avg_parse_confidence": 0.95,
            "empty_program_successes": 0,
            "failure_rate": failure_rate,
            "retry_events": 0,
            "timeout_count": 0,
            "top_error_codes": [],
            "browser_use_cost_usd_total": 0.1,
            "avg_cost_per_success": 0.1,
            "duration_seconds": 60.0,
        },
        "by_domain": [],
        "errors": [],
        "items": [],
    }


def test_ops_run_json_output(monkeypatch) -> None:
    monkeypatch.setattr("atlas.cli.commands.ops.run_ops_cycle", lambda _opts: _run_summary())

    runner = CliRunner()
    result = runner.invoke(app, ["ops", "run", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["run_id"] == "run-1"


def test_ops_run_exits_with_code_2_when_failure_rate_exceeds_threshold(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.cli.commands.ops.run_ops_cycle",
        lambda _opts: _run_summary(failure_rate=0.75, failed=3),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["ops", "run", "--failure-rate-threshold", "0.2"])
    assert result.exit_code == 2


def test_ops_dry_run_uses_dry_mode(monkeypatch) -> None:
    observed = {}

    def _fake_run(options):
        observed["dry_run"] = options.dry_run
        observed["persist_ledger"] = options.persist_ledger
        return _run_summary()

    monkeypatch.setattr("atlas.cli.commands.ops.run_ops_cycle", _fake_run)

    runner = CliRunner()
    result = runner.invoke(app, ["ops", "dry-run", "--json"])
    assert result.exit_code == 0
    assert observed == {"dry_run": True, "persist_ledger": False}


def test_ops_metrics_json_output(monkeypatch) -> None:
    monkeypatch.setattr("atlas.cli.commands.ops.read_recent_run_records", lambda _path, limit: [{"run_id": "x"}])
    monkeypatch.setattr(
        "atlas.cli.commands.ops.summarize_run_history",
        lambda _runs: {
            "runs_analyzed": 1,
            "latest_run_id": "x",
            "latest_completed_at": "2026-01-01T00:00:00+00:00",
            "totals": {
                "processed": 1,
                "succeeded": 1,
                "failed": 0,
                "blocked": 0,
                "skipped": 0,
                "browser_use_cost_usd_total": 0.1,
                "duration_seconds_total": 60.0,
            },
            "avg_failure_rate": 0.0,
            "max_failure_rate": 0.0,
            "top_error_codes": [],
        },
    )

    runner = CliRunner()
    result = runner.invoke(app, ["ops", "metrics", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["runs_analyzed"] == 1


def test_ops_backlog_json_output(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.cli.commands.ops.build_backlog_report",
        lambda _session, **_kwargs: {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "stale_after_days": 14,
            "totals": {
                "domains_count": 1,
                "sources_total": 10,
                "pending": 3,
                "succeeded": 6,
                "failed": 1,
                "stale_succeeded": 2,
            },
            "by_domain": [],
        },
    )

    class _SessionCtx:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr("atlas.cli.commands.ops.SessionLocal", lambda: _SessionCtx())

    runner = CliRunner()
    result = runner.invoke(app, ["ops", "backlog", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["totals"]["pending"] == 3


def test_ops_domain_quality_json_output(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.cli.commands.ops.build_domain_quality_report",
        lambda _session, **_kwargs: {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "totals": {
                "domains_count": 1,
                "admitted": 1,
                "blocked": 0,
            },
            "by_domain": [
                {
                    "domain": "example.com",
                    "allowlisted": True,
                    "paused": False,
                    "policy_present": True,
                    "admission_policy_enabled": True,
                    "admitted": True,
                    "admission_block_reason": None,
                    "succeeded_sources": 10,
                    "recent_crawl_window": 20,
                    "recent_attempted_crawls": 20,
                    "recent_failed_crawls": 1,
                    "recent_failure_rate": 0.05,
                    "avg_parse_confidence": 0.9,
                    "succeeded_with_documents": 10,
                    "zero_program_succeeded_sources": 1,
                    "zero_program_rate": 0.1,
                    "thresholds": {},
                }
            ],
        },
    )
    monkeypatch.setattr("atlas.cli.commands.ops.load_domain_policies", lambda _path: {})

    class _SessionCtx:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr("atlas.cli.commands.ops.SessionLocal", lambda: _SessionCtx())

    runner = CliRunner()
    result = runner.invoke(app, ["ops", "domain-quality", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["totals"]["admitted"] == 1
