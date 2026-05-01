from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI

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
