from __future__ import annotations

import asyncio
import os

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

        if request.method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            if len(body) > max_bytes:
                return JSONResponse({"detail": "request_body_too_large", "limit_bytes": max_bytes}, status_code=413)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
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
        if settings.app_env.lower() == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["Cache-Control"] = "no-store"
        return response


class AskRequestTimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/ask/"):
            return await call_next(request)
        settings = get_settings()
        timeout = max(1, int(settings.ask_request_timeout_seconds))
        try:
            return await asyncio.wait_for(call_next(request), timeout=timeout)
        except asyncio.TimeoutError:
            return JSONResponse({"status": "timeout", "detail": "request_timed_out"}, status_code=504)


def configure_security(app: FastAPI) -> None:
    settings = get_settings()
    origins = settings.csv_items(settings.cors_allowed_origins)
    hosts = settings.csv_items(settings.trusted_hosts)
    vercel_url = os.getenv("VERCEL_URL", "").strip().lower()
    if vercel_url and vercel_url not in hosts:
        hosts.append(vercel_url)
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
    app.add_middleware(AskRequestTimeoutMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
