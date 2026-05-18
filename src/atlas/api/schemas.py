from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from atlas.ask.contracts import AskAtlasResponse

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ProgramSearchItem(BaseModel):
    id: int
    name: str | None = None
    confidence: float | None = None
    document_id: int
    source_id: int | None = None
    canonical_url: str | None = None


class SourceSearchItem(BaseModel):
    id: int
    canonical_url: str
    status: str | None = None
    last_crawled_at: str | None = None


class SourceListItem(SourceSearchItem):
    domain: str | None = None
    title: str | None = None


class SourceDetailDocument(BaseModel):
    id: int
    html_storage_path: str | None = None
    extracted_json_storage_path: str | None = None


class SourceDetailCrawl(BaseModel):
    id: int
    status: str
    retry_count: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None
    browser_use_session_id: str | None = None
    browser_use_live_url: str | None = None
    browser_use_cost_usd: float | None = None


class SourceDetailProgram(BaseModel):
    id: int
    name: str | None = None
    confidence: float | None = None


class SourceDetailResponse(BaseModel):
    id: int
    domain: str | None = None
    canonical_url: str
    source_type: str | None = None
    title: str | None = None
    author: str | None = None
    status: str | None = None
    last_crawled_at: str | None = None
    document: SourceDetailDocument | None = None
    latest_crawl: SourceDetailCrawl | None = None
    programs: list[SourceDetailProgram]


class DashboardSummary(BaseModel):
    domains_total: int
    allowlisted_domains: int
    paused_domains: int
    sources_total: int
    sources_pending: int
    sources_succeeded: int
    sources_failed: int
    documents_total: int
    programs_total: int
    claims_total: int
    latest_successful_crawl_at: str | None = None
    recent_crawls_analyzed: int
    recent_crawls_failed: int


class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("invalid_email")
        return normalized


class AuthSessionResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None
    token_type: str = "bearer"


class AuthSignupResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    expires_in: int | None = None
    token_type: str = "bearer"
    user_id: str | None = None
    email: str | None = None
    email_confirmation_required: bool = False


class QuotaStatusResponse(BaseModel):
    status: str
    limit: int
    used: int
    remaining: int
    can_ask: bool
    contact_url: str | None = None


class RetrievalSourceCandidate(SourceSearchItem):
    rank: int


class RetrievalProgramCandidate(ProgramSearchItem):
    rank: int


class RetrievalEvidenceSelection(BaseModel):
    source_id: int
    document_id: int
    canonical_url: str
    title: str | None = None
    parse_confidence: float | None = None
    reason: str


class RetrievalDebugSummary(BaseModel):
    source_candidates: int
    program_candidates: int
    evidence_selected: int


class RetrievalDebugResponse(BaseModel):
    request_query: str
    filters: dict
    source_candidates: list[RetrievalSourceCandidate]
    program_candidates: list[RetrievalProgramCandidate]
    evidence: list[RetrievalEvidenceSelection]
    summary: RetrievalDebugSummary
    ask_response: AskAtlasResponse
