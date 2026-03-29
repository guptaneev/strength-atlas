from __future__ import annotations

import json
from datetime import UTC, datetime

from typer.testing import CliRunner

from atlas.cli.app import app
from atlas.db.models import CrawlJob, Document, Source


class _Result:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class _SessionCtx:
    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, *_args):
        return None


def test_source_show_json_contains_latest_crawl_metadata(monkeypatch) -> None:
    source = Source(
        id=6,
        url="https://example.com/how-to-bench",
        canonical_url="https://example.com/how-to-bench",
        domain_id=1,
        status="succeeded",
        latest_document_id=3,
        last_crawled_at=datetime(2026, 3, 28, tzinfo=UTC),
    )
    document = Document(
        id=3,
        source_id=6,
        crawl_job_id=5,
        html_storage_path="sources/6/crawls/5/raw.html",
        extracted_json_storage_path="sources/6/crawls/5/extracted.json",
    )
    crawl = CrawlJob(
        id=5,
        job_type="extract",
        source_id=6,
        target_url="https://example.com/how-to-bench",
        status="succeeded",
        retry_count=1,
        browser_use_session_id="sess-5",
        browser_use_live_url="https://live.example/sess-5",
        browser_use_cost_usd=0.23,
        started_at=datetime(2026, 3, 28, 22, 0, 0, tzinfo=UTC),
        completed_at=datetime(2026, 3, 28, 22, 1, 0, tzinfo=UTC),
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
            return _Result([])

    monkeypatch.setattr("atlas.cli.commands.source.SessionLocal", lambda: _SessionCtx(FakeSession()))
    runner = CliRunner()
    result = runner.invoke(app, ["source", "show", "--source-id", "6", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["document"]["html_storage_path"] == "sources/6/crawls/5/raw.html"
    assert payload["latest_crawl"]["id"] == 5
    assert payload["latest_crawl"]["status"] == "succeeded"
    assert payload["latest_crawl"]["retry_count"] == 1
