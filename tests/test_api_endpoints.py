from fastapi.testclient import TestClient

from atlas.api.app import app, get_db
from atlas.api.schemas import (
    DashboardSummary,
    ProgramSearchItem,
    RetrievalDebugResponse,
    SourceDetailResponse,
    SourceListItem,
    SourceSearchItem,
)
from atlas.ask.contracts import AskAtlasResponse, EvidenceCard


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_web_app_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/app")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_search_sources_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.app.run_source_search",
        lambda *_args, **_kwargs: [
            SourceSearchItem(
                id=1,
                canonical_url="https://example.com/source",
                status="succeeded",
                last_crawled_at="2026-04-29T00:00:00+00:00",
            )
        ],
    )
    app.dependency_overrides[get_db] = lambda: object()
    client = TestClient(app)
    response = client.get("/search/sources", params={"query": "bench"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["canonical_url"] == "https://example.com/source"


def test_sources_list_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.app.run_source_list",
        lambda *_args, **_kwargs: [
            SourceListItem(
                id=1,
                canonical_url="https://example.com/source",
                status="succeeded",
                last_crawled_at="2026-04-29T00:00:00+00:00",
                domain="example.com",
                title="A Source",
            )
        ],
    )
    app.dependency_overrides[get_db] = lambda: object()
    client = TestClient(app)
    response = client.get("/sources", params={"domain": "example.com", "status": "succeeded"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["domain"] == "example.com"


def test_source_detail_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.app.run_source_detail",
        lambda *_args, **_kwargs: SourceDetailResponse.model_validate(
            {
                "id": 1,
                "domain": "example.com",
                "canonical_url": "https://example.com/source",
                "source_type": "program_page",
                "title": "Source Title",
                "author": "Coach",
                "status": "succeeded",
                "last_crawled_at": "2026-04-29T00:00:00+00:00",
                "document": {
                    "id": 2,
                    "html_storage_path": "sources/1/crawls/2/raw.html",
                    "extracted_json_storage_path": "sources/1/crawls/2/extracted.json",
                },
                "latest_crawl": {
                    "id": 2,
                    "status": "succeeded",
                    "retry_count": 0,
                },
                "programs": [{"id": 4, "name": "Bench Builder", "confidence": 0.9}],
            }
        ),
    )
    app.dependency_overrides[get_db] = lambda: object()
    client = TestClient(app)
    response = client.get("/sources/1")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 1
    assert payload["document"]["id"] == 2


def test_source_detail_endpoint_not_found(monkeypatch) -> None:
    monkeypatch.setattr("atlas.api.app.run_source_detail", lambda *_args, **_kwargs: None)
    app.dependency_overrides[get_db] = lambda: object()
    client = TestClient(app)
    response = client.get("/sources/999")
    app.dependency_overrides.clear()
    assert response.status_code == 404


def test_dashboard_summary_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.app.run_dashboard_summary",
        lambda *_args, **_kwargs: DashboardSummary(
            domains_total=2,
            allowlisted_domains=2,
            paused_domains=0,
            sources_total=83,
            sources_pending=44,
            sources_succeeded=39,
            sources_failed=0,
            documents_total=50,
            programs_total=175,
            claims_total=476,
            latest_successful_crawl_at="2026-04-14T21:00:54+00:00",
            recent_crawls_analyzed=20,
            recent_crawls_failed=0,
        ),
    )
    app.dependency_overrides[get_db] = lambda: object()
    client = TestClient(app)
    response = client.get("/dashboard/summary")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["sources_total"] == 83


def test_search_programs_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.app.run_program_search",
        lambda *_args, **_kwargs: [
            ProgramSearchItem(
                id=2,
                name="Bench Builder",
                confidence=0.9,
                document_id=5,
                source_id=1,
                canonical_url="https://example.com/program",
            )
        ],
    )
    app.dependency_overrides[get_db] = lambda: object()
    client = TestClient(app)
    response = client.get("/search/programs", params={"query": "bench", "domain": "example.com"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["name"] == "Bench Builder"


def test_ask_retrieve_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.app.run_retrieval",
        lambda *_args, **_kwargs: AskAtlasResponse(
            answer="Retrieved evidence.",
            confidence=0.8,
            evidence=[
                EvidenceCard(
                    source_id=1,
                    document_id=2,
                    canonical_url="https://example.com/source",
                )
            ],
            status="ok",
        ),
    )
    app.dependency_overrides[get_db] = lambda: object()
    client = TestClient(app)
    response = client.post(
        "/ask/retrieve",
        json={
            "query": "bench frequency",
            "max_sources": 5,
            "max_programs": 10,
            "filters": {"domain": "example.com"},
        },
    )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["evidence"][0]["source_id"] == 1


def test_ask_retrieve_debug_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.app.run_retrieval_debug",
        lambda *_args, **_kwargs: RetrievalDebugResponse.model_validate(
            {
                "request_query": "bench frequency",
                "filters": {"domain": "example.com"},
                "source_candidates": [
                    {
                        "rank": 1,
                        "id": 1,
                        "canonical_url": "https://example.com/source",
                        "status": "succeeded",
                        "last_crawled_at": "2026-04-29T00:00:00+00:00",
                    }
                ],
                "program_candidates": [],
                "evidence": [
                    {
                        "source_id": 1,
                        "document_id": 2,
                        "canonical_url": "https://example.com/source",
                        "reason": "source_fallback",
                    }
                ],
                "summary": {
                    "source_candidates": 1,
                    "program_candidates": 0,
                    "evidence_selected": 1,
                },
                "ask_response": {
                    "answer": "Retrieved evidence.",
                    "status": "ok",
                    "evidence": [],
                },
            }
        ),
    )
    app.dependency_overrides[get_db] = lambda: object()
    client = TestClient(app)
    response = client.post(
        "/ask/retrieve/debug",
        json={
            "query": "bench frequency",
            "max_sources": 5,
            "max_programs": 10,
            "filters": {"domain": "example.com"},
        },
    )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["evidence_selected"] == 1


def test_ask_answer_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.app.run_answer",
        lambda *_args, **_kwargs: AskAtlasResponse(
            answer="Found grounded patterns.",
            confidence=0.75,
            evidence=[],
            status="ok",
        ),
    )
    app.dependency_overrides[get_db] = lambda: object()
    client = TestClient(app)
    response = client.post(
        "/ask/answer",
        json={
            "query": "bench frequency",
            "max_sources": 5,
            "max_programs": 10,
            "include_evidence": False,
            "max_evidence": 5,
            "filters": {"domain": "example.com"},
        },
    )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["confidence"] == 0.75
