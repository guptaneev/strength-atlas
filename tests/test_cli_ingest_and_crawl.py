from __future__ import annotations

import json
from dataclasses import dataclass

from typer.testing import CliRunner

from atlas.cli.app import app
from atlas.db.models import CrawlJob, Document, Source


class _ResultWrapper:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        if isinstance(self._value, list):
            return self._value
        return []


class _SessionCtx:
    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, *_args):
        return None


@dataclass
class _ActiveCrawl:
    id: int
    status: str


def test_ingest_discover_blocks_when_domain_has_active_crawl(monkeypatch) -> None:
    class FakeSession:
        def commit(self):
            return None

    monkeypatch.setattr("atlas.cli.commands.ingest.SessionLocal", lambda: _SessionCtx(FakeSession()))
    monkeypatch.setattr("atlas.cli.commands.ingest.is_domain_allowlisted", lambda _s, _d: True)
    monkeypatch.setattr(
        "atlas.cli.commands.ingest.get_active_crawl_for_domain",
        lambda _s, _d: _ActiveCrawl(id=42, status="running"),
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "ingest",
            "discover",
            "--domain",
            "example.com",
            "--seed-url",
            "https://example.com",
        ],
    )
    assert result.exit_code == 1
    assert "discover blocked" in result.stdout


def test_ingest_discover_timeout_returns_clean_error(monkeypatch) -> None:
    class FakeSession:
        def commit(self):
            return None

    monkeypatch.setattr("atlas.cli.commands.ingest.SessionLocal", lambda: _SessionCtx(FakeSession()))
    monkeypatch.setattr("atlas.cli.commands.ingest.is_domain_allowlisted", lambda _s, _d: True)
    monkeypatch.setattr("atlas.cli.commands.ingest.get_active_crawl_for_domain", lambda _s, _d: None)
    def _raise_timeout(coro):
        coro.close()
        raise TimeoutError("x")

    monkeypatch.setattr("atlas.cli.commands.ingest.run_async", _raise_timeout)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "ingest",
            "discover",
            "--domain",
            "example.com",
            "--seed-url",
            "https://example.com",
        ],
    )
    assert result.exit_code == 1
    assert "discover timeout" in result.stdout


def test_crawl_stop_noop_for_terminal_status(monkeypatch) -> None:
    class Crawl:
        def __init__(self):
            self.id = 1
            self.status = "succeeded"
            self.error_message = None
            self.browser_use_session_id = None

    class FakeSession:
        def __init__(self):
            self.row = Crawl()

        def get(self, _cls, _id):
            return self.row

        def commit(self):
            return None

    monkeypatch.setattr("atlas.cli.commands.crawl.SessionLocal", lambda: _SessionCtx(FakeSession()))
    runner = CliRunner()
    result = runner.invoke(app, ["crawl", "stop", "--crawl-id", "1"])
    assert result.exit_code == 0
    assert "no-op" in result.stdout


def test_crawl_stop_marks_running_job_failed(monkeypatch) -> None:
    class Crawl:
        def __init__(self):
            self.id = 2
            self.status = "running"
            self.error_message = None
            self.browser_use_session_id = "sess-2"
            self.completed_at = None

    class FakeSession:
        def __init__(self):
            self.row = Crawl()

        def get(self, _cls, _id):
            return self.row

        def commit(self):
            return None

    class FakeBrowserUseClient:
        async def stop_session(self, _session_id: str, strategy: str = "task"):
            return None

    monkeypatch.setattr("atlas.cli.commands.crawl.SessionLocal", lambda: _SessionCtx(FakeSession()))
    monkeypatch.setattr("atlas.cli.commands.crawl.BrowserUseClient", FakeBrowserUseClient)
    runner = CliRunner()
    result = runner.invoke(app, ["crawl", "stop", "--crawl-id", "2", "--json"])
    assert result.exit_code == 0
    assert '"status": "stopped"' in result.stdout


def test_ingest_diagnose_json_output(monkeypatch) -> None:
    source = Source(
        id=6,
        url="https://example.com/program-bundle",
        canonical_url="https://example.com/program-bundle",
        domain_id=1,
        latest_document_id=3,
        status="succeeded",
    )
    document = Document(
        id=3,
        source_id=6,
        crawl_job_id=5,
        extracted_json_storage_path="sources/6/crawls/5/extracted.json",
    )
    crawl = CrawlJob(
        id=5,
        job_type="extract",
        source_id=6,
        target_url=source.url,
        status="succeeded",
    )

    class FakeSession:
        def get(self, cls, obj_id):
            if cls is Source and obj_id == 6:
                return source
            if cls is Document and obj_id == 3:
                return document
            if cls is CrawlJob and obj_id == 5:
                return crawl
            return None

        def execute(self, _stmt):
            return _ResultWrapper([])

    class FakeStorage:
        def download_json_or_text(self, _path):
            return {"title": "Program Bundle", "main_text": "Body " * 40, "programs": []}

    monkeypatch.setattr("atlas.cli.commands.ingest.SessionLocal", lambda: _SessionCtx(FakeSession()))
    monkeypatch.setattr("atlas.cli.commands.ingest.SupabaseStorageClient", FakeStorage)
    runner = CliRunner()
    result = runner.invoke(app, ["ingest", "diagnose", "--source-id", "6", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["source_id"] == 6
    assert payload["document_id"] == 3
    assert "payload_type" in payload
    assert "validation_errors" in payload


def test_ingest_reextract_empty_uses_helper(monkeypatch) -> None:
    source = Source(
        id=6,
        url="https://example.com/program-bundle",
        canonical_url="https://example.com/program-bundle",
        domain_id=1,
        status="succeeded",
    )

    class FakeSession:
        def commit(self):
            return None

    class FakeStorage:
        pass

    class FakeClient:
        pass

    class FakeDoc:
        id = 77

    async def fake_extract(_session, _client, _url, _source, storage=None):
        assert storage is not None
        return FakeDoc()

    monkeypatch.setattr("atlas.cli.commands.ingest.SessionLocal", lambda: _SessionCtx(FakeSession()))
    monkeypatch.setattr("atlas.cli.commands.ingest.BrowserUseClient", lambda poll_timeout_seconds=None: FakeClient())
    monkeypatch.setattr("atlas.cli.commands.ingest.SupabaseStorageClient", FakeStorage)
    monkeypatch.setattr("atlas.cli.commands.ingest.get_active_crawl_for_domain", lambda _s, _d: None)
    monkeypatch.setattr("atlas.cli.commands.ingest._sources_with_empty_programs", lambda _s, domain, limit: [source])
    monkeypatch.setattr("atlas.cli.commands.ingest.extract_url", fake_extract)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["ingest", "reextract-empty", "--domain", "example.com", "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["queued"] == 1
    assert payload["succeeded"] == 1
