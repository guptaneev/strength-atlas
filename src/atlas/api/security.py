from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from atlas.config.settings import get_settings


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        max_bytes = int(settings.request_max_body_bytes)
        raw = request.headers.get("content-length")
        if raw:
            try:
                size = int(raw)
            except ValueError:
                size = 0
            if size > max_bytes:
                return JSONResponse({"detail": "request_body_too_large", "limit_bytes": max_bytes}, status_code=413)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        csp = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "font-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Content-Security-Policy"] = csp
        return response


def configure_security(app: FastAPI) -> None:
    settings = get_settings()
    origins = settings.csv_items(settings.cors_allowed_origins)
    hosts = settings.csv_items(settings.trusted_hosts)
    is_prod = settings.app_env.lower() == "production"
    if is_prod and "*" in origins:
        raise RuntimeError("Wildcard CORS origin is not allowed in production")

    if settings.enforce_https_redirect:
        app.add_middleware(HTTPSRedirectMiddleware)
    if not hosts:
        hosts = ["localhost", "127.0.0.1"]
    if not is_prod and "testserver" not in hosts:
        hosts.append("testserver")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["http://localhost:8000", "http://127.0.0.1:8000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
