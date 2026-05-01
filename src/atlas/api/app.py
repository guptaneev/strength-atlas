from __future__ import annotations

import asyncio
from collections.abc import Generator
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from atlas.api.auth import AuthUser, get_current_user, login_with_password, signup_with_password
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
    run_source_detail,
    run_source_list,
    run_source_search,
)
from atlas.ask.contracts import AskAnswerRequest, AskAtlasResponse, RetrievalRequest
from atlas.config.settings import get_settings
from atlas.db.engine import SessionLocal
from atlas.search.programs import ProgramSearchFilters

settings = get_settings()
docs_enabled = bool(settings.api_docs_enabled) and settings.app_env.lower() != "production"
app = FastAPI(
    title="Strength Atlas API",
    version="0.1.0",
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)
configure_security(app)

WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
STATIC_ROOT = WEB_ROOT / "static"
INDEX_HTML = WEB_ROOT / "templates" / "index.html"
if STATIC_ROOT.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_ROOT)), name="assets")

ASK_LIMITER = InMemoryRateLimiter()


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
def auth_error_handler(_request: Request, exc: AuthError) -> JSONResponse:
    return JSONResponse({"status": "auth_error", "detail": str(exc)}, status_code=401)


@app.exception_handler(QuotaExceededError)
def quota_error_handler(_request: Request, exc: QuotaExceededError) -> JSONResponse:
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
def rate_limit_error_handler(_request: Request, exc: RateLimitExceededError) -> JSONResponse:
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


@app.on_event("startup")
def startup_checks() -> None:
    if settings.app_env.lower() == "production":
        if not settings.database_url:
            raise RuntimeError("ATLAS_DATABASE_URL is required in production")
        if not settings.supabase_url:
            raise RuntimeError("ATLAS_SUPABASE_URL is required in production")


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


@app.get("/search/sources", response_model=list[SourceSearchItem])
def search_sources_endpoint(
    query: str = Query(..., min_length=1),
    domain: str | None = Query(None),
    limit: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_db),
) -> list[SourceSearchItem]:
    return run_source_search(
        session,
        query=query,
        domain=domain,
        limit=limit,
    )


@app.get("/sources", response_model=list[SourceListItem])
def list_sources_endpoint(
    domain: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db),
) -> list[SourceListItem]:
    return run_source_list(
        session,
        domain=domain,
        status=status,
        limit=limit,
    )


@app.get("/sources/{source_id}", response_model=SourceDetailResponse)
def source_detail_endpoint(
    source_id: int,
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
    query: str = Query("", min_length=0),
    days_per_week: int | None = Query(None),
    specialization: str | None = Query(None),
    experience_level: str | None = Query(None),
    progression_type: str | None = Query(None),
    split_type: str | None = Query(None),
    domain: str | None = Query(None),
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
            domain=domain,
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
