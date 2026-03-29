from __future__ import annotations

import json
import re
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
    structured_output: dict[str, Any]
    payload_type: str
    parse_confidence: float
    warnings: list[str]


def normalize_extraction(output: Any, *, url: str | None = None) -> NormalizedExtraction:
    original_output = output
    structured_output, payload_type = _coerce_to_structured_output(output)
    warnings: list[str] = []
    if payload_type != "object":
        warnings.append("schema_invalid")

    if payload_type == "object":
        output = structured_output
    else:
        output = {}

    raw_text_fallback = None
    if payload_type == "string":
        raw_text_fallback = _stringify(original_output)

    title = _first_non_empty(output, "title", "page_title", "headline", "name")
    author = _first_non_empty(output, "author", "byline")
    source_type = _first_non_empty(output, "source_type", "type")
    raw_text = _first_non_empty(output, "text", "raw_text", "content", "main_text", "body", "markdown")
    summary = _first_non_empty(output, "summary", "description", "excerpt")
    if not raw_text and raw_text_fallback:
        raw_text = raw_text_fallback

    programs = [_normalize_program(item) for item in _safe_list(output.get("programs"))]
    programs = [p for p in programs if p is not None]
    if not programs:
        inferred = infer_programs(url=url, title=title, summary=summary, raw_text=raw_text)
        if inferred:
            warnings.append("programs_inferred")
            programs = inferred

    claims = [_normalize_claim(item) for item in _safe_list(output.get("claims"))]
    claims = [c for c in claims if c is not None]

    parse_confidence = compute_parse_confidence(
        title=title,
        raw_text=raw_text,
        summary=summary,
        programs=programs,
        claims=claims,
        warnings=warnings,
    )

    return NormalizedExtraction(
        title=title,
        author=author,
        source_type=source_type,
        raw_text=raw_text,
        summary=summary,
        programs=programs,
        claims=claims,
        structured_output=_build_structured_output(
            title=title,
            author=author,
            source_type=source_type,
            summary=summary,
            raw_text=raw_text,
            programs=programs,
            claims=claims,
            original=structured_output if payload_type == "object" else {},
        ),
        payload_type=payload_type,
        parse_confidence=parse_confidence,
        warnings=warnings,
    )


def build_content_tsv_text(title: str | None, summary: str | None, raw_text: str | None) -> str:
    parts = [p for p in [title, summary, raw_text] if p]
    return "\n".join(parts)


def validate_normalized_extraction(normalized: NormalizedExtraction, *, url: str | None = None) -> list[str]:
    errors: list[str] = []
    if normalized.payload_type != "object":
        errors.append("schema_invalid")
        return errors

    text = (normalized.raw_text or "").strip()
    if len(text) < 80:
        errors.append("low_quality_output")
    elif _looks_like_extraction_meta_text(text):
        errors.append("low_quality_output")

    if is_program_focused_url(url) and not normalized.programs:
        errors.append("no_programs_on_program_page")
    return errors


def is_program_focused_url(url: str | None) -> bool:
    if not url:
        return False
    lowered = url.lower()
    return any(token in lowered for token in ("/program", "program-", "-program", "bundle", "template"))


def infer_programs(
    *,
    url: str | None,
    title: str | None,
    summary: str | None,
    raw_text: str | None,
) -> list[dict[str, Any]]:
    if not is_program_focused_url(url):
        return []

    seed_name = (title or "").strip()
    if not seed_name:
        return []

    program: dict[str, Any] = {
        "name": seed_name,
        "summary": (summary or "").strip() or _first_sentence(raw_text),
        "confidence": 0.35,
    }
    days = _parse_days_per_week(raw_text)
    if days is not None:
        program["days_per_week"] = days
    specialization = _normalize_specialization(seed_name or raw_text)
    if specialization:
        program["specialization"] = specialization
    return [program]


def compute_parse_confidence(
    *,
    title: str | None,
    raw_text: str | None,
    summary: str | None,
    programs: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    warnings: list[str],
) -> float:
    score = 0.2
    if title:
        score += 0.15
    text_len = len((raw_text or "").strip())
    if text_len >= 2000:
        score += 0.3
    elif text_len >= 500:
        score += 0.2
    elif text_len >= 120:
        score += 0.1
    if summary:
        score += 0.05
    if programs:
        score += 0.2
    if claims:
        score += 0.05
    if "schema_invalid" in warnings:
        score -= 0.25
    if "programs_inferred" in warnings:
        score -= 0.1
    return _clamp_confidence(score)


def _first_non_empty(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _coerce_to_structured_output(output: Any) -> tuple[dict[str, Any], str]:
    if hasattr(output, "model_dump"):
        dumped = output.model_dump()
        if isinstance(dumped, dict):
            return dumped, "object"
    if isinstance(output, dict):
        return output, "object"
    if isinstance(output, str):
        parsed = _parse_json_like_text(output)
        if isinstance(parsed, dict):
            return parsed, "object"
        return {}, "string"
    return {}, type(output).__name__


def _parse_json_like_text(text: str) -> Any | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", stripped, re.DOTALL | re.IGNORECASE)
    if fence:
        block = fence.group(1)
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            return None
    return None


def _normalize_program(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    name = _first_non_empty(value, "name", "program_name", "title")
    coach_name = _first_non_empty(value, "coach_name", "coach", "author")
    summary = _first_non_empty(value, "summary", "description")
    specialization = _normalize_specialization(_first_non_empty(value, "specialization", "focus"))
    experience_level = _normalize_experience_level(_first_non_empty(value, "experience_level", "experience"))
    progression_type = _normalize_progression_type(_first_non_empty(value, "progression_type", "progression"))
    split_type = _normalize_split_type(_first_non_empty(value, "split_type", "split"))
    days_per_week = _parse_days_per_week(value.get("days_per_week"))
    confidence = _clamp_confidence(value.get("confidence"))

    if not any(
        [
            name,
            coach_name,
            summary,
            specialization,
            experience_level,
            progression_type,
            split_type,
            days_per_week is not None,
        ]
    ):
        return None

    return {
        "name": name,
        "coach_name": coach_name,
        "days_per_week": days_per_week,
        "specialization": specialization,
        "experience_level": experience_level,
        "progression_type": progression_type,
        "split_type": split_type,
        "summary": summary,
        "confidence": confidence,
    }


def _normalize_claim(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    claim_type = _first_non_empty(value, "claim_type", "type")
    raw_text = _first_non_empty(value, "raw_text", "text", "claim")
    normalized_value = _first_non_empty(value, "normalized_value", "normalized")
    confidence = _clamp_confidence(value.get("confidence"))
    if not any([claim_type, raw_text, normalized_value]):
        return None
    return {
        "program_id": value.get("program_id"),
        "claim_type": claim_type,
        "raw_text": raw_text,
        "normalized_value": normalized_value,
        "confidence": confidence,
    }


def _build_structured_output(
    *,
    title: str | None,
    author: str | None,
    source_type: str | None,
    summary: str | None,
    raw_text: str | None,
    programs: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    original: dict[str, Any],
) -> dict[str, Any]:
    structured: dict[str, Any] = dict(original)
    structured["title"] = title
    structured["author"] = author
    structured["source_type"] = source_type
    structured["summary"] = summary
    structured["main_text"] = raw_text
    structured["programs"] = programs
    structured["claims"] = claims
    return structured


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _parse_days_per_week(value: Any) -> int | None:
    if isinstance(value, int):
        return value if 1 <= value <= 14 else None
    if isinstance(value, str):
        match = re.search(r"\b(\d{1,2})\b", value)
        if not match:
            return None
        days = int(match.group(1))
        return days if 1 <= days <= 14 else None
    return None


def _normalize_specialization(value: str | None) -> str | None:
    return _normalize_enum(
        value,
        {
            "bench": "bench",
            "squat": "squat",
            "deadlift": "deadlift",
            "powerlift": "powerlifting",
            "hypertrophy": "hypertrophy",
            "strength": "strength",
            "general": "general",
        },
    )


def _normalize_experience_level(value: str | None) -> str | None:
    return _normalize_enum(
        value,
        {
            "beginner": "beginner",
            "novice": "beginner",
            "intermediate": "intermediate",
            "advanced": "advanced",
            "expert": "advanced",
        },
    )


def _normalize_progression_type(value: str | None) -> str | None:
    return _normalize_enum(
        value,
        {
            "linear": "linear",
            "undulat": "undulating",
            "wave": "undulating",
            "autoreg": "autoregulated",
            "rpe": "autoregulated",
            "block": "block",
            "conjugate": "conjugate",
        },
    )


def _normalize_split_type(value: str | None) -> str | None:
    return _normalize_enum(
        value,
        {
            "full body": "full-body",
            "full-body": "full-body",
            "upper lower": "upper-lower",
            "upper-lower": "upper-lower",
            "push pull legs": "push-pull-legs",
            "push-pull-legs": "push-pull-legs",
            "body part": "body-part",
            "body-part": "body-part",
        },
    )


def _normalize_enum(value: str | None, mapping: dict[str, str]) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    if not lowered:
        return None
    for key, normalized in mapping.items():
        if key in lowered:
            return normalized
    return lowered


def _clamp_confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return None
    if as_float < 0:
        return 0.0
    if as_float > 1:
        return 1.0
    return as_float


def _first_sentence(text: str | None) -> str | None:
    if not text:
        return None
    stripped = text.strip()
    if not stripped:
        return None
    pieces = re.split(r"(?<=[.!?])\s+", stripped, maxsplit=1)
    sentence = pieces[0].strip()
    if len(sentence) > 220:
        return sentence[:220].rstrip() + "..."
    return sentence


def _looks_like_extraction_meta_text(text: str) -> bool:
    sample = text[:800].lower()
    patterns = (
        "the extracted data",
        "i have extracted",
        "saved to a json file",
        "file path:",
        "json includes",
        "complete data has been saved",
        "summary:",
    )
    return any(pattern in sample for pattern in patterns)


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return str(value)
    except Exception:
        return None
