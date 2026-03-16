import asyncio

from atlas.browser_use.client import BrowserUseResult
from atlas.db.models import Source
from atlas.ingest.extraction import extract_url
from atlas.ingest.refresh import refresh_source


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


class FakeClient:
    async def extract_url(self, url: str) -> BrowserUseResult:
        return BrowserUseResult(
            output={"title": "T", "author": "A", "text": "Body", "programs": [], "claims": []},
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


def test_refresh_source_runs_extraction() -> None:
    session = FakeSession()
    source = Source(url="https://example.com", canonical_url="https://example.com", domain_id=1)
    session.add(source)
    asyncio.run(refresh_source(session=session, client=FakeClient(), source_id=source.id))
    assert source.latest_document_id is not None
