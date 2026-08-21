"""Export retrieved claim evidence for offline answer-model experiments."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.api.service import run_retrieval_debug
from atlas.ask.contracts import RetrievalRequest
from atlas.db.models import Claim, Document, Source
from atlas.ml.dataset import RelevanceDataset
from atlas.search.programs import ProgramSearchFilters, search_programs


_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in", "is", "it",
    "of", "on", "or", "per", "program", "the", "this", "to", "week", "with",
}
_MARKDOWN_URL = re.compile(r"^\[([^\]]+)\]\(([^)]+)\)$")


def export_answer_evidence(
    session: Session,
    queries: RelevanceDataset,
    *,
    max_sources: int = 6,
    claims_per_source: int = 3,
) -> dict[str, Any]:
    """Snapshot only retrieved, source-attributed claims for a portable run.

    The export deliberately excludes credentials, raw database dumps, and user
    data.  A claim is included only when its document was selected by retrieval.
    """
    exported_queries: list[dict[str, Any]] = []
    for query in queries.queries:
        response = run_retrieval_debug(
            session,
            RetrievalRequest(query=query.query, max_sources=max_sources, max_programs=20),
        )
        evidence: list[dict[str, Any]] = []
        candidate_programs = list(response.program_candidates)
        structured_filters = ProgramSearchFilters(
            days_per_week=_as_int(query.intent.get("days_per_week")),
            experience_level=_as_str(query.intent.get("experience_level")),
            split_type=_as_str(query.intent.get("split_type")),
        )
        structured_programs = search_programs(
            session,
            None,
            structured_filters,
            limit=10,
        )
        existing_program_ids = {program.id for program in candidate_programs}
        candidate_programs.extend(
            _program_search_item(session, program)
            for program in structured_programs
            if program.id not in existing_program_ids
        )
        for program in candidate_programs:
            if not _program_matches_intent(program, query.intent):
                continue
            fields = [
                ("program", program.name),
                ("days per week", program.days_per_week),
                ("experience level", program.experience_level),
                ("specialization", program.specialization),
                ("progression", program.progression_type),
                ("split", program.split_type),
                ("summary", program.summary),
            ]
            text = "; ".join(f"{name}: {value}" for name, value in fields if value not in (None, ""))
            if not text:
                continue
            evidence.append({
                "evidence_id": f"program-{program.id}",
                "program_id": program.id,
                "canonical_url": _clean_url(program.canonical_url),
                "source_title": program.source_title,
                "text": text,
            })
        for selected in response.evidence:
            if selected.document_id <= 0:
                continue
            claims = session.scalars(
                select(Claim)
                .where(Claim.document_id == selected.document_id)
                .where(Claim.raw_text.is_not(None))
                .order_by(Claim.confidence.desc().nullslast(), Claim.id.asc())
                .limit(claims_per_source)
            ).all()
            claims = [claim for claim in claims if _query_overlap(query.query, claim.raw_text or "")]
            if not claims:
                continue
            source = session.get(Source, selected.source_id)
            document = session.get(Document, selected.document_id)
            if source is None or document is None:
                continue
            for claim in claims:
                text = (claim.raw_text or "").strip()
                if not text:
                    continue
                evidence.append({
                    "evidence_id": f"claim-{claim.id}",
                    "claim_id": claim.id,
                    "canonical_url": _clean_url(source.canonical_url),
                    "source_title": source.title,
                    "text": text,
                })
        if evidence:
            exported_queries.append({
                "query_id": query.query_id,
                "query": query.query,
                "evidence": evidence,
            })
    return {
        "version": 1,
        "kind": "strength_atlas_answer_evidence_export",
        "query_count": len(exported_queries),
        "queries": exported_queries,
    }


def _query_overlap(query: str, claim_text: str) -> int:
    """Return a small, inspectable lexical relevance score for claim export."""
    query_terms = _terms(query)
    claim_terms = _terms(claim_text)
    return len(query_terms & claim_terms)


def _terms(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if (len(token) > 2 or token.isdigit()) and token not in _STOP_WORDS
    }


def _program_matches_intent(program: Any, intent: dict[str, Any]) -> bool:
    """Keep program metadata only when it matches every explicit structured constraint."""
    matched = False
    expected_days = intent.get("days_per_week")
    if expected_days is not None:
        if program.days_per_week != int(expected_days):
            return False
        matched = True
    expected_level = intent.get("experience_level")
    if expected_level:
        if str(program.experience_level or "").lower() != str(expected_level).lower():
            return False
        matched = True
    expected_split = intent.get("split_type")
    if expected_split:
        if str(program.split_type or "").lower() != str(expected_split).lower():
            return False
        matched = True
    return matched


def _program_search_item(session: Session, program: Any) -> Any:
    """Adapt an ORM program into the fields used by the export formatter."""
    document = session.get(Document, program.document_id)
    source = session.get(Source, document.source_id) if document else None
    return type("StructuredProgram", (), {
        "id": program.id,
        "name": program.name,
        "days_per_week": program.days_per_week,
        "experience_level": program.experience_level,
        "specialization": program.specialization,
        "progression_type": program.progression_type,
        "split_type": program.split_type,
        "summary": program.summary,
        "canonical_url": source.canonical_url if source else "",
        "source_title": source.title if source else None,
    })()


def _as_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _as_str(value: Any) -> str | None:
    return str(value) if value else None


def _clean_url(value: Any) -> str:
    """Keep exports machine-readable when an upstream URL was Markdown-wrapped."""
    raw = str(value or "").strip()
    match = _MARKDOWN_URL.fullmatch(raw)
    return match.group(2).strip() if match else raw
