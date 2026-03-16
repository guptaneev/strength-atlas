from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class NormalizedExtraction:
    title: str | None
    author: str | None
    source_type: str | None
    raw_text: str | None
    summary: str | None
    programs: list[dict[str, Any]]
    claims: list[dict[str, Any]]


def normalize_extraction(output: Any) -> NormalizedExtraction:
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError:
            output = {}

    title = output.get("title")
    author = output.get("author")
    source_type = output.get("source_type")
    raw_text = output.get("text") or output.get("raw_text")
    summary = output.get("summary")
    programs = output.get("programs") or []
    claims = output.get("claims") or []

    return NormalizedExtraction(
        title=title,
        author=author,
        source_type=source_type,
        raw_text=raw_text,
        summary=summary,
        programs=programs,
        claims=claims,
    )


def build_content_tsv_text(title: str | None, summary: str | None, raw_text: str | None) -> str:
    parts = [p for p in [title, summary, raw_text] if p]
    return "\n".join(parts)
