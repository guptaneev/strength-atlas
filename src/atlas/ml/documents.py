"""Canonical program representation shared by labels, training, and inference."""

from __future__ import annotations

from atlas.db.models import Document, Program, Source


def program_document_text(program: Program, document: Document | None, source: Source | None) -> str:
    """Render program text with explicit metadata for cross-encoder input."""
    fields = [
        ("program", program.name),
        ("summary", program.summary),
        ("experience level", program.experience_level),
        ("days per week", program.days_per_week),
        ("specialization", program.specialization),
        ("progression", program.progression_type),
        ("split", program.split_type),
        ("coach", program.coach_name),
        ("source title", source.title if source else None),
        ("source url", source.canonical_url if source else None),
        ("source content", document.raw_text if document else None),
    ]
    return "\n".join(f"{name}: {value}" for name, value in fields if value not in (None, ""))
