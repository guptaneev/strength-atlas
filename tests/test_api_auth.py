from __future__ import annotations

from types import SimpleNamespace

import pytest

from atlas.api.auth import get_current_user, login_with_password, signup_with_password, verify_supabase_jwt
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


def test_verify_supabase_jwt_falls_back_to_userinfo(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.auth.get_settings",
        lambda: SimpleNamespace(
            supabase_url="https://example.supabase.co",
            supabase_publishable_key="anon-key",
            supabase_auth_timeout_seconds=10,
            supabase_jwt_audience="authenticated",
            supabase_jwt_issuer=None,
            supabase_jwks_url=None,
        ),
    )
    monkeypatch.setattr("atlas.api.auth._get_jwks", lambda: {})
    import jwt

    monkeypatch.setattr(jwt, "get_unverified_header", lambda _token: {"kid": "k1", "alg": "ES256"})
    monkeypatch.setattr(jwt, "decode", lambda *_args, **_kwargs: (_ for _ in ()).throw(jwt.InvalidTokenError()))

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"id": "user-1", "email": "u@example.com", "role": "authenticated"}

    monkeypatch.setattr("atlas.api.auth.httpx.get", lambda *_args, **_kwargs: _Resp())

    claims = verify_supabase_jwt("a.b.c")
    assert claims["sub"] == "user-1"
    assert claims["role"] == "authenticated"
