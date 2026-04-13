from types import SimpleNamespace

from atlas.ops.planner import PlannedSource
from atlas.ops.runner import OpsRunOptions, run_ops_cycle


class _SessionCtx:
    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, *_args):
        return None


class _FakeSession:
    def get(self, *_args, **_kwargs):
        return None


def test_run_ops_cycle_dry_run_plans_and_marks_items(monkeypatch) -> None:
    monkeypatch.setattr("atlas.ops.runner.SessionLocal", lambda: _SessionCtx(_FakeSession()))
    monkeypatch.setattr(
        "atlas.ops.runner.load_runnable_domains",
        lambda _session, _domains: ([SimpleNamespace(id=1, domain="example.com")], []),
    )
    monkeypatch.setattr("atlas.ops.runner.get_active_crawl_for_domain", lambda _s, _d: None)
    monkeypatch.setattr(
        "atlas.ops.runner.plan_sources_for_domain",
        lambda _session, domain_row, per_domain_limit, global_remaining: [
            PlannedSource(source_id=1, domain=domain_row.domain, canonical_url="https://a", mode="extract_pending"),
            PlannedSource(source_id=2, domain=domain_row.domain, canonical_url="https://b", mode="refresh_empty"),
        ],
    )

    summary = run_ops_cycle(
        OpsRunOptions(
            domains=["example.com"],
            per_domain_limit=10,
            global_limit=10,
            timeout_seconds=300,
            discover_first=False,
            discover_seed_urls=[],
            failure_rate_threshold=0.35,
            ledger_path="/tmp/unused.jsonl",
            dry_run=True,
            persist_ledger=False,
        )
    )

    assert summary["totals"]["sources_queued"] == 2
    assert summary["totals"]["skipped"] == 2
    assert all(item["status"] == "skipped" for item in summary["items"])


def test_run_ops_cycle_marks_domain_blocked_when_active_crawl_exists(monkeypatch) -> None:
    monkeypatch.setattr("atlas.ops.runner.SessionLocal", lambda: _SessionCtx(_FakeSession()))
    monkeypatch.setattr(
        "atlas.ops.runner.load_runnable_domains",
        lambda _session, _domains: ([SimpleNamespace(id=1, domain="example.com")], []),
    )
    monkeypatch.setattr(
        "atlas.ops.runner.get_active_crawl_for_domain",
        lambda _session, _domain: SimpleNamespace(id=99, status="running"),
    )

    summary = run_ops_cycle(
        OpsRunOptions(
            domains=["example.com"],
            per_domain_limit=10,
            global_limit=10,
            timeout_seconds=300,
            discover_first=False,
            discover_seed_urls=[],
            failure_rate_threshold=0.35,
            ledger_path="/tmp/unused.jsonl",
            dry_run=True,
            persist_ledger=False,
        )
    )

    assert summary["totals"]["sources_queued"] == 0
    assert summary["totals"]["blocked"] == 0
    assert summary["items"][0]["item_type"] == "domain_gate"
    assert summary["items"][0]["status"] == "blocked"


def test_run_ops_cycle_reuses_single_event_loop_for_multiple_items(monkeypatch) -> None:
    class _Source:
        def __init__(self, source_id: int, url: str, canonical_url: str):
            self.id = source_id
            self.url = url
            self.canonical_url = canonical_url
            self.latest_document_id = None

    class _Session:
        def __init__(self):
            self.sources = {
                1: _Source(1, "https://example.com/a", "https://example.com/a"),
                2: _Source(2, "https://example.com/b", "https://example.com/b"),
            }

        def get(self, cls, source_id):
            _ = cls
            return self.sources.get(source_id)

    class _Client:
        def __init__(self, poll_timeout_seconds=None):
            self.poll_timeout_seconds = poll_timeout_seconds
            self.closed = False

        async def close(self):
            self.closed = True

    class _Storage:
        pass

    class _Doc:
        def __init__(self, doc_id: int):
            self.id = doc_id

    seen_loop_ids: list[int] = []
    fake_client: _Client | None = None
    next_doc_id = 10

    async def _fake_extract(session, client, url, source, storage=None):
        nonlocal next_doc_id
        _ = session
        _ = url
        _ = source
        _ = storage
        import asyncio

        seen_loop_ids.append(id(asyncio.get_running_loop()))
        next_doc_id += 1
        return _Doc(next_doc_id)

    monkeypatch.setattr("atlas.ops.runner.SessionLocal", lambda: _SessionCtx(_Session()))
    monkeypatch.setattr(
        "atlas.ops.runner.load_runnable_domains",
        lambda _session, _domains: ([SimpleNamespace(id=1, domain="example.com")], []),
    )
    monkeypatch.setattr("atlas.ops.runner.get_active_crawl_for_domain", lambda _s, _d: None)
    monkeypatch.setattr(
        "atlas.ops.runner.plan_sources_for_domain",
        lambda _session, domain_row, per_domain_limit, global_remaining: [
            PlannedSource(source_id=1, domain=domain_row.domain, canonical_url="https://example.com/a", mode="extract_pending"),
            PlannedSource(source_id=2, domain=domain_row.domain, canonical_url="https://example.com/b", mode="extract_pending"),
        ],
    )
    monkeypatch.setattr("atlas.ops.runner.extract_url", _fake_extract)
    monkeypatch.setattr(
        "atlas.ops.runner._success_item",
        lambda **kwargs: {
            "item_type": kwargs["mode"],
            "mode": kwargs["mode"],
            "domain": kwargs["domain"],
            "source_id": kwargs["source"].id,
            "status": "succeeded",
            "program_count": 0,
            "parse_confidence": 0.9,
            "retry_count": 0,
            "cost_usd": 0.0,
        },
    )
    monkeypatch.setattr("atlas.ops.runner.SupabaseStorageClient", _Storage)

    def _build_client(poll_timeout_seconds=None):
        nonlocal fake_client
        fake_client = _Client(poll_timeout_seconds=poll_timeout_seconds)
        return fake_client

    monkeypatch.setattr("atlas.ops.runner.BrowserUseClient", _build_client)

    summary = run_ops_cycle(
        OpsRunOptions(
            domains=["example.com"],
            per_domain_limit=10,
            global_limit=10,
            timeout_seconds=300,
            discover_first=False,
            discover_seed_urls=[],
            failure_rate_threshold=0.35,
            ledger_path="/tmp/unused.jsonl",
            dry_run=False,
            persist_ledger=False,
        )
    )

    assert summary["totals"]["processed"] == 2
    assert summary["totals"]["succeeded"] == 2
    assert len(seen_loop_ids) == 2
    assert seen_loop_ids[0] == seen_loop_ids[1]
    assert fake_client is not None
    assert fake_client.closed is True
