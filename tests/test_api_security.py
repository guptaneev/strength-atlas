from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from atlas.api.security import configure_security


def test_configure_security_rejects_wildcard_cors_in_production(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.security.get_settings",
        lambda: SimpleNamespace(
            app_env="production",
            cors_allowed_origins="*",
            trusted_hosts="example.com",
            enforce_https_redirect=True,
            request_max_body_bytes=1024,
            csv_items=lambda value: [item.strip() for item in value.split(",") if item.strip()],
        ),
    )
    with pytest.raises(RuntimeError, match="Wildcard CORS origin"):
        configure_security(FastAPI())


def test_security_adds_hsts_in_production(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.security.get_settings",
        lambda: SimpleNamespace(
            app_env="production",
            cors_allowed_origins="https://atlas.example.com",
            trusted_hosts="atlas.example.com",
            enforce_https_redirect=False,
            request_max_body_bytes=1024,
            ask_request_timeout_seconds=5,
            csv_items=lambda value: [item.strip() for item in value.split(",") if item.strip()],
        ),
    )
    app = FastAPI()
    configure_security(app)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    client = TestClient(app)
    response = client.get("/health", headers={"host": "atlas.example.com"})
    assert response.status_code == 200
    assert response.headers["strict-transport-security"].startswith("max-age=31536000")


def test_vercel_url_is_allowed_host(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL_URL", "strength-atlas-git-main.vercel.app")
    monkeypatch.setattr(
        "atlas.api.security.get_settings",
        lambda: SimpleNamespace(
            app_env="production",
            cors_allowed_origins="https://strength-atlas-git-main.vercel.app",
            trusted_hosts="localhost,127.0.0.1",
            enforce_https_redirect=False,
            request_max_body_bytes=1024,
            ask_request_timeout_seconds=5,
            csv_items=lambda value: [item.strip() for item in value.split(",") if item.strip()],
        ),
    )
    app = FastAPI()
    configure_security(app)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    client = TestClient(app)
    response = client.get("/health", headers={"host": "strength-atlas-git-main.vercel.app"})
    assert response.status_code == 200


def test_request_size_limit_checks_body(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.security.get_settings",
        lambda: SimpleNamespace(
            app_env="development",
            cors_allowed_origins="http://localhost:8000",
            trusted_hosts="localhost,testserver",
            enforce_https_redirect=False,
            request_max_body_bytes=20,
            ask_request_timeout_seconds=5,
            csv_items=lambda value: [item.strip() for item in value.split(",") if item.strip()],
        ),
    )
    app = FastAPI()
    configure_security(app)

    @app.post("/echo")
    async def echo():
        return {"status": "ok"}

    client = TestClient(app)
    response = client.post("/echo", json={"x": "this payload exceeds configured max bytes"})
    assert response.status_code == 413
    assert response.json()["detail"] == "request_body_too_large"


def test_cors_preflight_allows_only_configured_origin(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.security.get_settings",
        lambda: SimpleNamespace(
            app_env="production",
            cors_allowed_origins="https://atlas.example.com",
            trusted_hosts="atlas.example.com",
            enforce_https_redirect=False,
            request_max_body_bytes=1024,
            ask_request_timeout_seconds=5,
            csv_items=lambda value: [item.strip() for item in value.split(",") if item.strip()],
        ),
    )
    app = FastAPI()
    configure_security(app)
    client = TestClient(app)
    allowed = client.options(
        "/ask/answer",
        headers={
            "host": "atlas.example.com",
            "origin": "https://atlas.example.com",
            "access-control-request-method": "POST",
        },
    )
    denied = client.options(
        "/ask/answer",
        headers={
            "host": "atlas.example.com",
            "origin": "https://evil.example.com",
            "access-control-request-method": "POST",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://atlas.example.com"
    assert denied.status_code == 400


def test_https_redirect_is_enforced(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.security.get_settings",
        lambda: SimpleNamespace(
            app_env="production",
            cors_allowed_origins="https://atlas.example.com",
            trusted_hosts="atlas.example.com",
            enforce_https_redirect=True,
            request_max_body_bytes=1024,
            ask_request_timeout_seconds=5,
            csv_items=lambda value: [item.strip() for item in value.split(",") if item.strip()],
        ),
    )
    app = FastAPI()
    configure_security(app)
    client = TestClient(app, follow_redirects=False)
    response = client.get("http://atlas.example.com/health")
    assert response.status_code in {307, 308}
    assert response.headers["location"].startswith("https://")


def test_ask_timeout_middleware(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.security.get_settings",
        lambda: SimpleNamespace(
            app_env="development",
            cors_allowed_origins="http://localhost:8000",
            trusted_hosts="localhost,testserver",
            enforce_https_redirect=False,
            request_max_body_bytes=4096,
            ask_request_timeout_seconds=1,
            csv_items=lambda value: [item.strip() for item in value.split(",") if item.strip()],
        ),
    )
    app = FastAPI()
    configure_security(app)

    @app.post("/ask/slow")
    async def slow():
        await asyncio.sleep(2)
        return {"status": "ok"}

    client = TestClient(app)
    response = client.post("/ask/slow", json={"q": "bench"})
    assert response.status_code == 504
    assert response.json()["status"] == "timeout"
