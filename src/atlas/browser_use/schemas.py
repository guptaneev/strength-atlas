from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProgramPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    coach_name: str | None = None
    days_per_week: int | str | None = None
    specialization: str | None = None
    experience_level: str | None = None
    progression_type: str | None = None
    split_type: str | None = None
    summary: str | None = None
    confidence: float | str | None = None


class ClaimPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    program_id: int | str | None = None
    claim_type: str | None = None
    raw_text: str | None = None
    normalized_value: str | None = None
    confidence: float | str | None = None


class ExtractionPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = None
    author: str | None = None
    source_type: str | None = None
    summary: str | None = None
    main_text: str | None = None
    text: str | None = None
    raw_text: str | None = None
    raw_html: str | None = None
    programs: list[ProgramPayload] = Field(default_factory=list)
    claims: list[ClaimPayload] = Field(default_factory=list)
