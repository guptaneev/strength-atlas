from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from atlas.api.schemas import (
    DashboardSummary,
    ProgramSearchItem,
    RetrievalDebugResponse,
    SourceDetailResponse,
    SourceListItem,
    SourceSearchItem,
)
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
from atlas.db.engine import SessionLocal
from atlas.search.programs import ProgramSearchFilters

app = FastAPI(title="Strength Atlas API", version="0.1.0")
WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
STATIC_ROOT = WEB_ROOT / "static"
INDEX_HTML = WEB_ROOT / "templates" / "index.html"
if STATIC_ROOT.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_ROOT)), name="assets")


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        close = getattr(session, "close", None)
        if callable(close):
            close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
    session: Session = Depends(get_db),
) -> AskAtlasResponse:
    return run_retrieval(session, request)


@app.post("/ask/retrieve/debug", response_model=RetrievalDebugResponse)
def ask_retrieve_debug_endpoint(
    request: RetrievalRequest,
    session: Session = Depends(get_db),
) -> RetrievalDebugResponse:
    return run_retrieval_debug(session, request)


@app.post("/ask/answer", response_model=AskAtlasResponse)
def ask_answer_endpoint(
    request: AskAnswerRequest,
    session: Session = Depends(get_db),
) -> AskAtlasResponse:
    return run_answer(session, request)
