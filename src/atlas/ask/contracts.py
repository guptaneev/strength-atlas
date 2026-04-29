from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RetrievalFilters(BaseModel):
    domain: str | None = None
    days_per_week: int | None = None
    specialization: str | None = None
    experience_level: str | None = None
    progression_type: str | None = None
    split_type: str | None = None


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1)
    max_sources: int = Field(default=8, ge=1, le=50)
    max_programs: int = Field(default=20, ge=1, le=100)
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)


class EvidenceCard(BaseModel):
    source_id: int
    document_id: int
    canonical_url: str
    title: str | None = None
    snippet: str | None = None
    parse_confidence: float | None = None
    last_crawled_at: str | None = None


class AskAtlasResponse(BaseModel):
    answer: str
    confidence: float | None = None
    evidence: list[EvidenceCard] = Field(default_factory=list)
    status: Literal["ok", "insufficient_evidence"] = "ok"


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
