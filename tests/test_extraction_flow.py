import asyncio
from types import SimpleNamespace

import pytest

from atlas.browser_use.client import BrowserUseResult
from atlas.db.models import CrawlJob
from atlas.db.models import Source
from atlas.ingest.extraction import ExtractValidationError, extract_url
from atlas.ingest.refresh import refresh_source


LONG_BODY = "This is a sufficiently long extraction body. " * 12


class FakeSession:
    def __init__(self) -> None:
        self._id = 1
        self._objects = []
        self._by_id = {}

    def add(self, obj) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = self._id
            self._id += 1
        self._objects.append(obj)
        self._by_id[(obj.__class__, obj.id)] = obj

    def commit(self) -> None:
        return None

    def flush(self) -> None:
        return None

    def get(self, cls, obj_id):
        return self._by_id.get((cls, obj_id))

    def rollback(self) -> None:
        return None


class FakeClient:
    async def extract_url(self, url: str, model: str | None = None) -> BrowserUseResult:
        return BrowserUseResult(
            output={"title": "T", "author": "A", "main_text": LONG_BODY, "programs": [], "claims": []},
            session_id="sess",
            live_url="live",
            status="succeeded",
            total_cost_usd=0.01,
        )


class FakeStorage:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str, object]] = []

    def upload_text(self, object_path: str, text: str, _content_type: str) -> None:
        self.uploads.append(("text", object_path, text))

    def upload_json(self, object_path: str, payload) -> None:
        self.uploads.append(("json", object_path, payload))


class FlakyClient:
    def __init__(self, failures_before_success: int) -> None:
        self.failures_before_success = failures_before_success
        self.calls = 0

    async def extract_url(self, _url: str, model: str | None = None) -> BrowserUseResult:
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise TimeoutError("temporary timeout")
        return BrowserUseResult(
            output={"title": "T", "author": "A", "main_text": LONG_BODY, "programs": [], "claims": []},
            session_id="sess",
            live_url="live",
            status="succeeded",
            total_cost_usd=0.01,
        )


class UnstructuredClient:
    async def extract_url(self, _url: str, model: str | None = None) -> BrowserUseResult:
        return BrowserUseResult(
            output="I extracted the data and saved it to JSON file path: /workspace/foo.json",
            session_id="sess",
            live_url="live",
            status="succeeded",
            total_cost_usd=0.01,
        )


def test_extract_url_updates_source_and_document() -> None:
    session = FakeSession()
    source = Source(url="https://example.com", canonical_url="https://example.com", domain_id=1)
    session.add(source)
    doc = asyncio.run(extract_url(session=session, client=FakeClient(), url=source.url, source=source))
    assert doc.source_id == source.id
    assert source.latest_document_id == doc.id
    assert source.status == "succeeded"
    assert doc.parse_confidence is not None


def test_refresh_source_runs_extraction() -> None:
    session = FakeSession()
    source = Source(url="https://example.com", canonical_url="https://example.com", domain_id=1)
    session.add(source)
    asyncio.run(refresh_source(session=session, client=FakeClient(), source_id=source.id))
    assert source.latest_document_id is not None


def test_extract_url_uploads_storage_artifacts() -> None:
    session = FakeSession()
    source = Source(url="https://example.com", canonical_url="https://example.com", domain_id=1)
    session.add(source)
    storage = FakeStorage()
    asyncio.run(
        extract_url(
            session=session,
            client=FakeClient(),
            url=source.url,
            source=source,
            storage=storage,
        )
    )
    assert any(
        kind == "text" and path.startswith("sources/1/crawls/") and path.endswith("/raw.html")
        for kind, path, _payload in storage.uploads
    )
    json_uploads = [u for u in storage.uploads if u[0] == "json"]
    assert json_uploads
    assert json_uploads[0][1].startswith("sources/1/crawls/")
    assert json_uploads[0][1].endswith("/extracted.json")
    assert isinstance(json_uploads[0][2], dict)
    assert "main_text" in json_uploads[0][2]


def test_extract_url_retries_then_succeeds(monkeypatch) -> None:
    session = FakeSession()
    source = Source(url="https://example.com", canonical_url="https://example.com", domain_id=1)
    session.add(source)
    monkeypatch.setattr(
        "atlas.ingest.extraction.get_settings",
        lambda: SimpleNamespace(
            max_crawl_retries=2,
            browser_use_extract_model_primary="bu-mini",
            browser_use_extract_model_fallback="bu-max",
        ),
    )
    client = FlakyClient(failures_before_success=1)
    doc = asyncio.run(extract_url(session=session, client=client, url=source.url, source=source))
    assert doc.id is not None
    crawl_jobs = [obj for obj in session._objects if isinstance(obj, CrawlJob)]
    assert crawl_jobs[-1].retry_count == 1
    assert crawl_jobs[-1].status == "succeeded"


def test_extract_url_exhausts_retries(monkeypatch) -> None:
    session = FakeSession()
    source = Source(url="https://example.com", canonical_url="https://example.com", domain_id=1)
    session.add(source)
    monkeypatch.setattr(
        "atlas.ingest.extraction.get_settings",
        lambda: SimpleNamespace(
            max_crawl_retries=1,
            browser_use_extract_model_primary="bu-mini",
            browser_use_extract_model_fallback="bu-max",
        ),
    )
    client = FlakyClient(failures_before_success=10)
    with pytest.raises(TimeoutError):
        asyncio.run(extract_url(session=session, client=client, url=source.url, source=source))
    crawl_jobs = [obj for obj in session._objects if isinstance(obj, CrawlJob)]
    assert crawl_jobs[-1].retry_count == 1
    assert crawl_jobs[-1].status == "failed"


def test_extract_url_unstructured_output_retries_then_fails(monkeypatch) -> None:
    session = FakeSession()
    source = Source(url="https://example.com/program-bundle", canonical_url="https://example.com/program-bundle", domain_id=1)
    session.add(source)
    monkeypatch.setattr(
        "atlas.ingest.extraction.get_settings",
        lambda: SimpleNamespace(
            max_crawl_retries=1,
            browser_use_extract_model_primary="bu-mini",
            browser_use_extract_model_fallback="bu-max",
        ),
    )
    with pytest.raises(ExtractValidationError):
        asyncio.run(extract_url(session=session, client=UnstructuredClient(), url=source.url, source=source))
    crawl_jobs = [obj for obj in session._objects if isinstance(obj, CrawlJob)]
    assert crawl_jobs[-1].retry_count == 1
    assert crawl_jobs[-1].status == "failed"
    assert "schema_invalid" in (crawl_jobs[-1].error_message or "")
