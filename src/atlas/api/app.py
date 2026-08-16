from __future__ import annotations

import asyncio
import logging
from collections.abc import Generator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Path as ApiPath, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from atlas.api.auth import AuthUser, auth_readiness, get_current_user, login_with_password, signup_with_password
from atlas.api.errors import AuthError, QuotaExceededError, RateLimitExceededError
from atlas.api.quota import consume_ask_quota, get_quota_snapshot
from atlas.api.rate_limit import InMemoryRateLimiter, RateLimitRule
from atlas.api.schemas import (
    AuthLoginRequest,
    AuthSessionResponse,
    AuthSignupResponse,
    DashboardSummary,
    ProgramSearchItem,
    QuotaStatusResponse,
    RetrievalDebugResponse,
    RetrievalStatusResponse,
    SourceDetailResponse,
    SourceListItem,
    SourceSearchItem,
)
from atlas.api.security import configure_security
from atlas.api.service import (
    run_answer,
    run_dashboard_summary,
    run_program_search,
    run_retrieval,
    run_retrieval_debug,
    run_retrieval_status,
    run_source_detail,
    run_source_list,
    run_source_search,
)
from atlas.ask.contracts import AskAnswerRequest, AskAtlasResponse, RetrievalRequest
from atlas.config.settings import get_settings
from atlas.db.engine import SessionLocal
from atlas.search.programs import ProgramSearchFilters

settings = get_settings()
logger = logging.getLogger("atlas.api")
docs_enabled = bool(settings.api_docs_enabled) and settings.app_env.lower() != "production"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    startup_checks()
    yield


app = FastAPI(
    title="Strength Atlas API",
    version="0.1.0",
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
    lifespan=lifespan,
)
configure_security(app)

WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
STATIC_ROOT = WEB_ROOT / "static"
INDEX_HTML = WEB_ROOT / "templates" / "index.html"
ABOUT_HTML = WEB_ROOT / "templates" / "about.html"
PRIVACY_HTML = WEB_ROOT / "templates" / "privacy.html"
TERMS_HTML = WEB_ROOT / "templates" / "terms.html"
if STATIC_ROOT.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_ROOT)), name="assets")

ASK_LIMITER = InMemoryRateLimiter()
DOMAIN_QUERY_PATTERN = r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        close = getattr(session, "close", None)
        if callable(close):
            close()


@app.exception_handler(AuthError)
def auth_error_handler(request: Request, exc: AuthError) -> JSONResponse:
    detail = _public_auth_error_detail(exc)
    logger.warning(
        "auth_error path=%s method=%s detail=%s public_detail=%s request_id=%s",
        request.url.path,
        request.method,
        str(exc),
        detail,
        request.headers.get("x-request-id", ""),
    )
    return JSONResponse({"status": "auth_error", "detail": detail}, status_code=401)


@app.exception_handler(QuotaExceededError)
def quota_error_handler(request: Request, exc: QuotaExceededError) -> JSONResponse:
    logger.info(
        "quota_exceeded path=%s method=%s used=%s limit=%s request_id=%s",
        request.url.path,
        request.method,
        exc.used,
        exc.limit,
        request.headers.get("x-request-id", ""),
    )
    return JSONResponse(
        QuotaStatusResponse(
            status="quota_exceeded",
            limit=exc.limit,
            used=exc.used,
            remaining=exc.remaining,
            can_ask=False,
            contact_url=exc.contact_url,
        ).model_dump(),
        status_code=429,
    )


@app.exception_handler(RateLimitExceededError)
def rate_limit_error_handler(request: Request, exc: RateLimitExceededError) -> JSONResponse:
    logger.warning(
        "rate_limited path=%s method=%s key=%s retry_after_seconds=%s request_id=%s",
        request.url.path,
        request.method,
        exc.key,
        exc.retry_after_seconds,
        request.headers.get("x-request-id", ""),
    )
    return JSONResponse(
        {
            "status": "rate_limited",
            "detail": "too_many_requests",
            "retry_after_seconds": exc.retry_after_seconds,
        },
        status_code=429,
        headers={"Retry-After": str(exc.retry_after_seconds)},
    )


@app.exception_handler(asyncio.TimeoutError)
def timeout_error_handler(_request: Request, _exc: asyncio.TimeoutError) -> JSONResponse:
    return JSONResponse({"status": "timeout", "detail": "request_timed_out"}, status_code=504)


@app.exception_handler(Exception)
def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_api_error path=%s method=%s error_type=%s request_id=%s",
        request.url.path,
        request.method,
        exc.__class__.__name__,
        request.headers.get("x-request-id", ""),
    )
    return JSONResponse({"status": "error", "detail": "internal_server_error"}, status_code=500)


def startup_checks() -> None:
    if settings.app_env.lower() == "production":
        required_vars = {
            "ATLAS_DATABASE_URL": settings.database_url,
            "ATLAS_SUPABASE_URL": settings.supabase_url,
            "ATLAS_SUPABASE_PUBLISHABLE_KEY": settings.supabase_publishable_key,
            "ATLAS_CORS_ALLOWED_ORIGINS": settings.cors_allowed_origins,
            "ATLAS_TRUSTED_HOSTS": settings.trusted_hosts,
        }
        missing = [key for key, value in required_vars.items() if not value]
        if missing:
            raise RuntimeError(f"Missing required production config: {', '.join(sorted(missing))}")
        if settings.cors_allowed_origins.strip() == "*":
            raise RuntimeError("ATLAS_CORS_ALLOWED_ORIGINS cannot be wildcard in production")
        origins = settings.csv_items(settings.cors_allowed_origins)
        if any(origin.startswith("http://") or "localhost" in origin or "127.0.0.1" in origin for origin in origins):
            raise RuntimeError("Production CORS origins must use HTTPS and cannot be localhost")
        hosts = settings.csv_items(settings.trusted_hosts)
        if "*" in hosts or any(host in {"localhost", "127.0.0.1"} for host in hosts):
            raise RuntimeError("Production trusted hosts must be explicit public hostnames")
        if not settings.enforce_https_redirect:
            raise RuntimeError("ATLAS_ENFORCE_HTTPS_REDIRECT must be enabled in production")
        if settings.ask_lifetime_limit < 1:
            raise RuntimeError("ATLAS_ASK_LIFETIME_LIMIT must be >= 1")
        if settings.reranker_model_path and not settings.reranker_weights_sha256:
            raise RuntimeError("ATLAS_RERANKER_WEIGHTS_SHA256 is required when reranking is enabled")


def _rate_limit_ask(request: Request, user: AuthUser) -> None:
    ip = request.client.host if request.client else "unknown"
    ASK_LIMITER.check(
        f"ask_ip:{ip}",
        RateLimitRule(
            window_seconds=settings.ask_ip_rate_limit_window_seconds,
            max_requests=settings.ask_ip_rate_limit_max_requests,
        ),
    )
    ASK_LIMITER.check(
        f"ask_user:{user.user_id}",
        RateLimitRule(
            window_seconds=settings.ask_user_rate_limit_window_seconds,
            max_requests=settings.ask_user_rate_limit_max_requests,
        ),
    )


def _public_auth_error_detail(exc: AuthError) -> str:
    raw = str(exc)
    if raw in {
        "missing_authorization_header",
        "invalid_authorization_header",
        "token_verification_failed",
        "token_role_not_authenticated",
        "missing_token_subject",
        "unknown_signing_key",
    }:
        return raw
    if raw.startswith("supabase_auth_rejected:"):
        return "invalid_email_or_password"
    if raw.startswith("supabase_auth_request_failed:"):
        return "auth_provider_unavailable"
    if raw.startswith("jwks_fetch_failed:"):
        return "auth_provider_unavailable"
    return "auth_failed"


def _normalize_domain(domain: str | None) -> str | None:
    if domain is None:
        return None
    normalized = domain.strip().lower()
    return normalized or None


def _consume_quota(session: Session, user: AuthUser) -> QuotaStatusResponse:
    snapshot = consume_ask_quota(session, user_id=user.user_id)
    session.commit()
    return QuotaStatusResponse(
        status="ok",
        limit=snapshot.limit,
        used=snapshot.used,
        remaining=snapshot.remaining,
        can_ask=snapshot.can_ask,
        contact_url=settings.ask_contact_cta_url,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/retrieval/status", response_model=RetrievalStatusResponse)
def retrieval_status_endpoint() -> RetrievalStatusResponse:
    return run_retrieval_status()


@app.get("/ready")
def ready() -> JSONResponse:
    diagnostics: dict[str, str] = {"status": "ok"}

    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        diagnostics["database"] = f"unhealthy:{exc.__class__.__name__}"
        diagnostics["status"] = "degraded"

    auth_ok, auth_detail = auth_readiness()
    if not auth_ok:
        diagnostics["auth"] = auth_detail
        diagnostics["status"] = "degraded"
    else:
        diagnostics["auth"] = "ok"

    if diagnostics["status"] != "ok":
        return JSONResponse(diagnostics, status_code=503)
    return JSONResponse(diagnostics, status_code=200)


@app.post("/auth/login", response_model=AuthSessionResponse)
def login_endpoint(request: AuthLoginRequest) -> AuthSessionResponse:
    payload = login_with_password(request.email, request.password)
    return AuthSessionResponse(
        access_token=str(payload.get("access_token")),
        refresh_token=payload.get("refresh_token"),
        expires_in=payload.get("expires_in"),
        token_type=str(payload.get("token_type") or "bearer"),
    )


@app.post("/auth/signup", response_model=AuthSignupResponse)
def signup_endpoint(request: AuthLoginRequest) -> AuthSignupResponse:
    payload = signup_with_password(request.email, request.password)
    user = payload.get("user") or {}
    access_token = payload.get("access_token")
    return AuthSignupResponse(
        access_token=str(access_token) if access_token else None,
        refresh_token=payload.get("refresh_token"),
        expires_in=payload.get("expires_in"),
        token_type=str(payload.get("token_type") or "bearer"),
        user_id=str(user.get("id")) if user.get("id") else None,
        email=str(user.get("email")) if user.get("email") else request.email,
        email_confirmation_required=access_token is None,
    )


@app.get("/me/quota", response_model=QuotaStatusResponse)
def me_quota_endpoint(
    user: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> QuotaStatusResponse:
    snapshot = get_quota_snapshot(session, user_id=user.user_id)
    return QuotaStatusResponse(
        status="ok",
        limit=snapshot.limit,
        used=snapshot.used,
        remaining=snapshot.remaining,
        can_ask=snapshot.can_ask,
        contact_url=settings.ask_contact_cta_url,
    )


@app.get("/", include_in_schema=False)
def web_root() -> RedirectResponse:
    return RedirectResponse(url="/app")


@app.get("/app", include_in_schema=False)
def web_app() -> FileResponse:
    if not INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail="web_app_not_found")
    return FileResponse(str(INDEX_HTML))


@app.get("/about", include_in_schema=False)
def about_page() -> FileResponse:
    if not ABOUT_HTML.exists():
        raise HTTPException(status_code=404, detail="about_page_not_found")
    return FileResponse(str(ABOUT_HTML))


@app.get("/privacy", include_in_schema=False)
def privacy_page() -> FileResponse:
    if not PRIVACY_HTML.exists():
        raise HTTPException(status_code=404, detail="privacy_page_not_found")
    return FileResponse(str(PRIVACY_HTML))


@app.get("/terms", include_in_schema=False)
def terms_page() -> FileResponse:
    if not TERMS_HTML.exists():
        raise HTTPException(status_code=404, detail="terms_page_not_found")
    return FileResponse(str(TERMS_HTML))


@app.get("/search/sources", response_model=list[SourceSearchItem])
def search_sources_endpoint(
    query: str = Query(..., min_length=1, max_length=400),
    domain: str | None = Query(None, max_length=253, pattern=DOMAIN_QUERY_PATTERN),
    limit: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_db),
) -> list[SourceSearchItem]:
    return run_source_search(
        session,
        query=query,
        domain=_normalize_domain(domain),
        limit=limit,
    )


@app.get("/sources", response_model=list[SourceListItem])
def list_sources_endpoint(
    domain: str | None = Query(None, max_length=253, pattern=DOMAIN_QUERY_PATTERN),
    status: Literal["pending", "succeeded", "failed"] | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db),
) -> list[SourceListItem]:
    return run_source_list(
        session,
        domain=_normalize_domain(domain),
        status=status,
        limit=limit,
    )


@app.get("/sources/{source_id}", response_model=SourceDetailResponse)
def source_detail_endpoint(
    source_id: int = ApiPath(..., ge=1),
    session: Session = Depends(get_db),
) -> SourceDetailResponse:
    result = run_source_detail(session, source_id=source_id)
    if result is None:
        raise HTTPException(status_code=404, detail="source_not_found")
    return result


@app.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary_endpoint(session: Session = Depends(get_db)) -> DashboardSummary:
    return run_dashboard_summary(session)


@app.get("/search/programs", response_model=list[ProgramSearchItem])
def search_programs_endpoint(
    query: str = Query("", min_length=0, max_length=400),
    days_per_week: int | None = Query(None),
    specialization: str | None = Query(None),
    experience_level: str | None = Query(None),
    progression_type: str | None = Query(None),
    split_type: str | None = Query(None),
    domain: str | None = Query(None, max_length=253, pattern=DOMAIN_QUERY_PATTERN),
    limit: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_db),
) -> list[ProgramSearchItem]:
    return run_program_search(
        session,
        query=query,
        filters=ProgramSearchFilters(
            days_per_week=days_per_week,
            specialization=specialization,
            experience_level=experience_level,
            progression_type=progression_type,
            split_type=split_type,
            domain=_normalize_domain(domain),
        ),
        limit=limit,
    )


@app.post("/ask/retrieve", response_model=AskAtlasResponse)
def ask_retrieve_endpoint(
    request: RetrievalRequest,
    http_request: Request,
    user: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> AskAtlasResponse:
    _rate_limit_ask(http_request, user)
    _consume_quota(session, user)
    return run_retrieval(session, request)


@app.post("/ask/retrieve/debug", response_model=RetrievalDebugResponse)
def ask_retrieve_debug_endpoint(
    request: RetrievalRequest,
    http_request: Request,
    user: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> RetrievalDebugResponse:
    if settings.app_env.lower() == "production":
        raise HTTPException(status_code=404, detail="not_found")
    _rate_limit_ask(http_request, user)
    _consume_quota(session, user)
    return run_retrieval_debug(session, request)


@app.post("/ask/answer", response_model=AskAtlasResponse)
def ask_answer_endpoint(
    request: AskAnswerRequest,
    http_request: Request,
    user: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> AskAtlasResponse:
    _rate_limit_ask(http_request, user)
    _consume_quota(session, user)
    return run_answer(session, request)
