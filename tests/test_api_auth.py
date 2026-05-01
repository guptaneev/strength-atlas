from __future__ import annotations

from types import SimpleNamespace

import pytest

from atlas.api.auth import get_current_user, login_with_password, signup_with_password
from atlas.api.errors import AuthError


def test_get_current_user_requires_header() -> None:
    with pytest.raises(AuthError, match="missing_authorization_header"):
        get_current_user(None)


def test_get_current_user_rejects_invalid_scheme() -> None:
    with pytest.raises(AuthError, match="invalid_authorization_header"):
        get_current_user("Basic abc")


def test_login_with_password_requires_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.auth.get_settings",
        lambda: SimpleNamespace(supabase_url=None, supabase_publishable_key=None, supabase_auth_timeout_seconds=10),
    )
    with pytest.raises(AuthError, match="supabase_auth_login_not_configured"):
        login_with_password("a@example.com", "pw")


def test_signup_with_password_requires_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.auth.get_settings",
        lambda: SimpleNamespace(supabase_url=None, supabase_publishable_key=None, supabase_auth_timeout_seconds=10),
    )
    with pytest.raises(AuthError, match="supabase_auth_signup_not_configured"):
        signup_with_password("a@example.com", "pw")
