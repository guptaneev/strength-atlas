"""Transparent intent expansion for high-recall program candidate retrieval.

This is deliberately not labelled as embedding search. It is a deterministic
bridge between exact full-text retrieval and a future vector retriever: every
expansion and inferred constraint is inspectable and testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_PHRASE_EXPANSIONS = {
    "bench press": ("bench", "bench press"),
    "bench-focused": ("bench", "bench press"),
    "powerlifting": ("powerlifting", "powerlift"),
    "powerbuilding": ("powerbuilding", "powerbuild", "strength", "hypertrophy"),
    "hypertrophy": ("hypertrophy", "bodybuilding", "muscle"),
    "bodybuilding": ("bodybuilding", "hypertrophy", "muscle"),
    "meet prep": ("meet", "competition", "peaking", "powerlifting"),
    "first meet": ("meet", "competition", "novice", "beginner", "powerlifting"),
    "rehabilitation": ("rehab", "return", "injury"),
    "injury": ("injury", "rehab", "return"),
    "limited time": ("time", "minimal", "efficient", "low volume"),
    "minimum effective dose": ("minimal", "minimum", "low volume", "efficient"),
    "home gym": ("home", "equipment", "gym"),
    "full body": ("full-body", "full body"),
    "upper lower": ("upper-lower", "upper lower"),
    "post novice": ("intermediate", "novice"),
}

_TOKEN_EXPANSIONS = {
    "novice": ("novice", "beginner"),
    "beginner": ("beginner", "novice"),
    "intermediate": ("intermediate", "post-novice"),
    "advanced": ("advanced", "experienced"),
    "squat": ("squat", "squatting"),
    "deadlift": ("deadlift", "deadlifting"),
    "peaking": ("peaking", "competition", "meet"),
}


@dataclass(frozen=True)
class QueryIntent:
    terms: tuple[str, ...]
    days_per_week: int | None = None
    experience_level: str | None = None
    split_type: str | None = None


def expand_query(query: str) -> QueryIntent:
    """Return deduplicated retrieval terms and only high-confidence intent hints."""
    normalized = query.lower().replace("–", "-").strip()
    terms: list[str] = []
    consumed = normalized
    for phrase, expansions in _PHRASE_EXPANSIONS.items():
        if phrase in normalized:
            terms.extend(expansions)
            consumed = consumed.replace(phrase, " ")
    for token in re.findall(r"[a-z0-9]+", consumed):
        terms.extend(_TOKEN_EXPANSIONS.get(token, (token,)))

    days = _infer_days(normalized)
    experience = _infer_experience(normalized)
    split = "full-body" if "full body" in normalized else "upper-lower" if "upper lower" in normalized else None
    return QueryIntent(tuple(_dedupe(terms)), days, experience, split)


def _infer_days(query: str) -> int | None:
    match = re.search(r"\b([2-6])\s*-?\s*days?\b", query)
    if match:
        return int(match.group(1))
    words = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
    for word, value in words.items():
        if re.search(rf"\b{word}\s*-?\s*days?\b", query):
            return value
    return None


def _infer_experience(query: str) -> str | None:
    if "post novice" in query or "intermediate" in query:
        return "intermediate"
    if "novice" in query or "beginner" in query or "first meet" in query:
        return "beginner"
    if "advanced" in query:
        return "advanced"
    return None


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = value.strip().lower()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result
