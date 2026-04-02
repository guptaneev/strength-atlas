import asyncio
from types import SimpleNamespace

import pytest

from atlas.browser_use.client import BrowserUseResult
from atlas.db.models import CrawlJob
from atlas.ingest.discovery import DiscoveryResult, discover_and_create_sources


class FakeSession:
    def __init__(self) -> None:
        self._id = 1
        self._objects = []

    def add(self, obj) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = self._id
            self._id += 1
        self._objects.append(obj)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class FakeDiscoverClient:
    def __init__(self, failures_before_success: int = 0) -> None:
        self.calls = 0
        self.failures_before_success = failures_before_success

    async def discover_urls(self, domain: str, seed_urls: list[str]) -> BrowserUseResult:
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise TimeoutError("temporary timeout")
        return BrowserUseResult(
            output='["https://example.com/a"]',
            session_id="sess-1",
            live_url="https://live.example/sess-1",
            status="idle",
            total_cost_usd=0.11,
        )


def test_discover_persists_metadata_and_succeeds(monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setattr(
        "atlas.ingest.discovery.get_settings",
        lambda: SimpleNamespace(max_crawl_retries=2),
    )
    monkeypatch.setattr(
        "atlas.ingest.discovery.create_sources_from_urls",
        lambda _session, _domain, _candidate_urls: DiscoveryResult(created_sources=[], skipped_urls=[]),
    )
    result = asyncio.run(
        discover_and_create_sources(
            session=session,
            client=FakeDiscoverClient(failures_before_success=0),
            domain="example.com",
            seed_urls=["https://example.com"],
        )
    )
    assert result.crawl_job is not None
    assert result.crawl_job.status == "succeeded"
    assert result.crawl_job.browser_use_session_id == "sess-1"
    assert result.crawl_job.browser_use_cost_usd == 0.11


def test_discover_retries_then_fails(monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setattr(
        "atlas.ingest.discovery.get_settings",
        lambda: SimpleNamespace(max_crawl_retries=1),
    )
    monkeypatch.setattr(
        "atlas.ingest.discovery.create_sources_from_urls",
        lambda _session, _domain, _candidate_urls: DiscoveryResult(created_sources=[], skipped_urls=[]),
    )
    with pytest.raises(TimeoutError):
        asyncio.run(
            discover_and_create_sources(
                session=session,
                client=FakeDiscoverClient(failures_before_success=10),
                domain="example.com",
                seed_urls=["https://example.com"],
            )
        )
    crawl_jobs = [obj for obj in session._objects if isinstance(obj, CrawlJob)]
    assert crawl_jobs[-1].retry_count == 1
    assert crawl_jobs[-1].status == "failed"
