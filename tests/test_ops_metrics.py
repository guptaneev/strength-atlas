from atlas.ops.metrics import build_run_summary, summarize_run_history


def test_build_run_summary_computes_expected_fields() -> None:
    items = [
        {
            "item_type": "extract_pending",
            "mode": "extract_pending",
            "domain": "example.com",
            "status": "succeeded",
            "program_count": 3,
            "parse_confidence": 0.9,
            "retry_count": 1,
            "cost_usd": 0.1,
        },
        {
            "item_type": "refresh_empty",
            "mode": "refresh_empty",
            "domain": "example.com",
            "status": "failed",
            "error_code": "timeout",
            "retry_count": 2,
            "cost_usd": 0.2,
        },
    ]
    summary = build_run_summary(
        run_id="run-1",
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:10:00+00:00",
        duration_seconds=600.0,
        policy={"failure_rate_threshold": 0.35},
        domains_scanned=1,
        sources_queued=2,
        items=items,
    )

    totals = summary["totals"]
    assert totals["processed"] == 2
    assert totals["succeeded"] == 1
    assert totals["failed"] == 1
    assert totals["programs_created_total"] == 3
    assert totals["retry_events"] == 3
    assert totals["timeout_count"] == 1
    assert totals["browser_use_cost_usd_total"] == 0.30000000000000004


def test_summarize_run_history_aggregates_multiple_runs() -> None:
    runs = [
        {
            "run_id": "r1",
            "completed_at": "2026-01-01T00:00:00+00:00",
            "totals": {
                "processed": 2,
                "succeeded": 1,
                "failed": 1,
                "blocked": 0,
                "skipped": 0,
                "failure_rate": 0.5,
                "browser_use_cost_usd_total": 0.1,
            },
            "errors": [{"code": "timeout", "count": 1}],
        },
        {
            "run_id": "r2",
            "completed_at": "2026-01-02T00:00:00+00:00",
            "totals": {
                "processed": 3,
                "succeeded": 3,
                "failed": 0,
                "blocked": 0,
                "skipped": 0,
                "failure_rate": 0.0,
                "browser_use_cost_usd_total": 0.2,
            },
            "errors": [],
        },
    ]
    summary = summarize_run_history(runs)
    assert summary["runs_analyzed"] == 2
    assert summary["latest_run_id"] == "r2"
    assert summary["totals"]["processed"] == 5
    assert summary["totals"]["failed"] == 1
    assert summary["avg_failure_rate"] == 0.25
    assert summary["top_error_codes"][0]["code"] == "timeout"
