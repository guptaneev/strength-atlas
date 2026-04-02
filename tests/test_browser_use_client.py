import asyncio

import pytest

from atlas.browser_use.client import BrowserUseClient
from atlas.browser_use.schemas import ExtractionPayload


class FakeRunResult:
    def __init__(self, output=None):
        self.output = output if output is not None else {"ok": True}
        self.id = "sess-123"
        self.live_url = "https://live.example/sess-123"
        self.status = "idle"
        self.total_cost_usd = "0.17"


class FakeClient(BrowserUseClient):
    def __init__(self, result: FakeRunResult | None = None, exc: Exception | None = None):
        self._result = result
        self._exc = exc
        self.last_run_kwargs = None

    async def _run(self, _prompt: str, **kwargs):
        self.last_run_kwargs = kwargs
        if self._exc:
            raise self._exc
        return self._result


def test_browser_use_discover_extract_refresh_map_metadata() -> None:
    client = FakeClient(result=FakeRunResult(output={"title": "T", "main_text": "Body"}))

    discover = asyncio.run(client.discover_urls("example.com", ["https://example.com"]))
    assert discover.session_id == "sess-123"
    assert discover.live_url == "https://live.example/sess-123"
    assert discover.total_cost_usd == 0.17

    extract = asyncio.run(client.extract_url("https://example.com/program", model="bu-mini"))
    assert extract.session_id == "sess-123"
    assert extract.total_cost_usd == 0.17
    assert extract.output["title"] == "T"
    assert client.last_run_kwargs["model"] == "bu-mini"
    assert client.last_run_kwargs["output_schema"] is ExtractionPayload

    refresh = asyncio.run(client.refresh_source("1"))
    assert refresh.session_id == "sess-123"
    assert refresh.total_cost_usd == 0.17


def test_browser_use_extract_uses_workspace_json_fallback() -> None:
    class WorkspaceFallbackClient(FakeClient):
        async def _load_workspace_json_from_output(self, session_id: str, output_text: str):
            assert session_id == "sess-123"
            assert "/workspace/file.json" in output_text
            return {"title": "Recovered", "main_text": "Recovered body"}

    client = WorkspaceFallbackClient(result=FakeRunResult(output="saved at /workspace/file.json"))
    extract = asyncio.run(client.extract_url("https://example.com/program"))
    assert extract.output["title"] == "Recovered"


def test_browser_use_client_propagates_run_failure() -> None:
    client = FakeClient(exc=TimeoutError("timed out"))
    with pytest.raises(TimeoutError):
        asyncio.run(client.extract_url("https://example.com/program"))
