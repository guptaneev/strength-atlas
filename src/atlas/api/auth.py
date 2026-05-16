from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Header

from atlas.api.errors import AuthError
from atlas.config.settings import get_settings


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    email: str | None
    claims: dict[str, Any]
    token: str


_JWKS_CACHE: dict[str, Any] = {"expires_at": 0.0, "keys": {}}
_JWKS_LOCK = threading.Lock()


def get_current_user(authorization: str | None = Header(None)) -> AuthUser:
    if not authorization:
        raise AuthError("missing_authorization_header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthError("invalid_authorization_header")
    claims = verify_supabase_jwt(token.strip())
    sub = str(claims.get("sub") or "").strip()
    if not sub:
        raise AuthError("missing_token_subject")
    email = claims.get("email")
    return AuthUser(user_id=sub, email=str(email) if email else None, claims=claims, token=token.strip())


def verify_supabase_jwt(token: str) -> dict[str, Any]:
    settings = get_settings()
    _ensure_jwt_deps()
    import jwt  # type: ignore
    from jwt import InvalidTokenError  # type: ignore

    try:
        jwks = _get_jwks()
        header = jwt.get_unverified_header(token)
        kid = str(header.get("kid") or "")
        alg = str(header.get("alg") or "")
        if not kid or kid not in jwks:
            raise AuthError("unknown_signing_key")
        if alg not in {"RS256", "ES256", "EdDSA"}:
            raise AuthError(f"unsupported_signing_algorithm:{alg or 'unknown'}")

        key = _load_public_key_from_jwk(jwt, jwks[kid], alg)
        issuer = settings.supabase_jwt_issuer or _default_issuer(settings)
        claims = jwt.decode(
            token,
            key=key,
            algorithms=[alg],
            audience=settings.supabase_jwt_audience,
            issuer=issuer,
            options={"require": ["sub", "exp", "aud", "iss"]},
        )
    except InvalidTokenError as exc:
        raise AuthError("token_verification_failed") from exc
    except Exception as exc:  # noqa: BLE001
        raise AuthError("token_verification_failed") from exc
    if claims.get("role") != "authenticated":
        raise AuthError("token_role_not_authenticated")
    return claims


def login_with_password(email: str, password: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise AuthError("supabase_auth_login_not_configured")
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/token?grant_type=password"
    body = {"email": email, "password": password}
    headers = {
        "apikey": settings.supabase_publishable_key,
        "Content-Type": "application/json",
    }
    try:
        response = httpx.post(
            url,
            json=body,
            headers=headers,
            timeout=float(settings.supabase_auth_timeout_seconds),
        )
    except Exception as exc:  # noqa: BLE001
        raise AuthError(f"supabase_auth_request_failed:{exc}") from exc

    if response.status_code >= 400:
        raise AuthError(_format_supabase_auth_error(response))
    payload = response.json()
    token = str(payload.get("access_token") or "")
    if not token:
        raise AuthError("supabase_auth_missing_access_token")
    return payload


def signup_with_password(email: str, password: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise AuthError("supabase_auth_signup_not_configured")
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/signup"
    body = {"email": email, "password": password}
    headers = {
        "apikey": settings.supabase_publishable_key,
        "Content-Type": "application/json",
    }
    try:
        response = httpx.post(
            url,
            json=body,
            headers=headers,
            timeout=float(settings.supabase_auth_timeout_seconds),
        )
    except Exception as exc:  # noqa: BLE001
        raise AuthError(f"supabase_auth_request_failed:{exc}") from exc
    if response.status_code >= 400:
        raise AuthError(_format_supabase_auth_error(response))
    return response.json()


def _get_jwks() -> dict[str, dict[str, Any]]:
    settings = get_settings()
    now = time.time()
    with _JWKS_LOCK:
        if _JWKS_CACHE["keys"] and now < float(_JWKS_CACHE["expires_at"]):
            return _JWKS_CACHE["keys"]
    if not settings.supabase_url and not settings.supabase_jwks_url:
        raise AuthError("supabase_jwks_not_configured")

    jwks_url = settings.supabase_jwks_url or f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    try:
        response = httpx.get(jwks_url, timeout=float(settings.supabase_auth_timeout_seconds))
    except Exception as exc:  # noqa: BLE001
        raise AuthError(f"jwks_fetch_failed:{exc}") from exc
    if response.status_code >= 400:
        raise AuthError(f"jwks_fetch_failed:{response.status_code}")
    payload = response.json()
    keys = {}
    for item in payload.get("keys", []):
        kid = str(item.get("kid") or "")
        if kid:
            keys[kid] = item
    if not keys:
        raise AuthError("jwks_empty")
    with _JWKS_LOCK:
        _JWKS_CACHE["keys"] = keys
        _JWKS_CACHE["expires_at"] = time.time() + 300
    return keys


def auth_readiness() -> tuple[bool, str]:
    settings = get_settings()
    if not settings.supabase_url:
        return False, "missing_supabase_url"
    if not settings.supabase_publishable_key:
        return False, "missing_supabase_publishable_key"
    try:
        _get_jwks()
    except AuthError as exc:
        return False, f"jwks_unavailable:{exc}"
    except Exception:
        return False, "jwks_unavailable"
    return True, "ok"


def _default_issuer(settings) -> str:
    if not settings.supabase_url:
        raise AuthError("supabase_issuer_not_configured")
    return f"{settings.supabase_url.rstrip('/')}/auth/v1"


def _ensure_jwt_deps() -> None:
    try:
        import jwt  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        raise AuthError("jwt_library_not_installed") from exc


def _format_supabase_auth_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001
        return f"supabase_auth_rejected:{response.status_code}"
    code = payload.get("code")
    msg = payload.get("msg") or payload.get("message") or payload.get("error_description") or payload.get("error")
    parts = [f"supabase_auth_rejected:{response.status_code}"]
    if code:
        parts.append(str(code))
    if msg:
        parts.append(str(msg))
    return " | ".join(parts)


def _load_public_key_from_jwk(jwt_module, jwk: dict[str, Any], alg: str):
    py_jwk = getattr(jwt_module, "PyJWK", None)
    if py_jwk is not None:
        try:
            return py_jwk.from_dict(jwk).key
        except Exception:
            pass

    algorithms = jwt_module.algorithms.get_default_algorithms()
    algorithm_impl = algorithms.get(alg)
    if algorithm_impl is None:
        raise AuthError(f"unsupported_signing_algorithm:{alg}")
    return algorithm_impl.from_jwk(json.dumps(jwk))
