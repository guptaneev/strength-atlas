from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
)


class RetrievalFilters(BaseModel):
    domain: str | None = Field(default=None, max_length=253)
    days_per_week: int | None = None
    specialization: str | None = None
    experience_level: str | None = None
    progression_type: str | None = None
    split_type: str | None = None

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if not _DOMAIN_PATTERN.fullmatch(normalized):
            raise ValueError("invalid_domain_filter")
        return normalized


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=400)
    max_sources: int = Field(default=8, ge=1, le=50)
    max_programs: int = Field(default=20, ge=1, le=100)
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query_must_not_be_blank")
        return normalized


class EvidenceCard(BaseModel):
    source_id: int
    document_id: int
    canonical_url: str
    title: str | None = None
    snippet: str | None = None
    parse_confidence: float | None = None
    last_crawled_at: str | None = None
    domain: str | None = None
    source_title: str | None = None
    published_at: str | None = None


class AskAtlasResponse(BaseModel):
    answer: str
    confidence: float | None = None
    evidence: list[EvidenceCard] = Field(default_factory=list)
    status: Literal["ok", "insufficient_evidence"] = "ok"
    answer_mode: str = "deterministic"
    answer_model_version: str | None = None
    answer_fallback_reason: str | None = None


class AskAnswerRequest(RetrievalRequest):
    include_evidence: bool = True
    max_evidence: int = Field(default=8, ge=1, le=25)


class EmbeddingHookPayload(BaseModel):
    document_id: int
    source_id: int
    raw_text: str
    title: str | None = None
    summary: str | None = None


class EmbeddingHookResult(BaseModel):
    document_id: int
    embedded: bool
    embedding_model: str | None = None
    error: str | None = None
