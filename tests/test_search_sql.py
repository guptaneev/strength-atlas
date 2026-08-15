from sqlalchemy.dialects import postgresql

from atlas.search.programs import (
    ProgramSearchFilters,
    build_program_candidate_fallback_statement,
    build_program_search_statement,
)
from atlas.search.sources import build_source_search_statement


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect())).lower()


def test_program_search_uses_full_text_rank_and_order_chain() -> None:
    stmt = build_program_search_statement(
        query="bench",
        filters=ProgramSearchFilters(
            days_per_week=4,
            specialization="bench",
            experience_level="intermediate",
            progression_type="linear",
            split_type="upper-lower",
            domain="example.com",
        ),
        limit=25,
    )
    sql = _sql(stmt)
    assert "plainto_tsquery" in sql
    assert "ts_rank" in sql
    assert "order by" in sql
    assert "case when" in sql
    assert "ts_rank(documents.content_tsv" in sql
    assert "canonical_url ilike" in sql
    assert "programs.confidence desc" in sql
    assert "coalesce(crawl_jobs.started_at, documents.created_at, programs.created_at) desc" in sql


def test_source_search_dedupes_via_grouped_source_subquery() -> None:
    stmt = build_source_search_statement(query="bench", domain="example.com", limit=25)
    sql = _sql(stmt)
    assert "group by documents.source_id" in sql
    assert "max(ts_rank" in sql
    assert "join (" in sql
    assert "source_id" in sql
    assert "canonical_url ilike" in sql


def test_program_candidate_fallback_uses_expanded_lexical_candidates_and_intent_boosts() -> None:
    stmt = build_program_candidate_fallback_statement(
        query="beginner powerlifting program four days per week",
        filters=ProgramSearchFilters(),
        limit=50,
    )
    sql = _sql(stmt)
    assert "plainto_tsquery" in sql
    assert " || " in sql
    assert "programs.days_per_week" in sql
    assert "programs.experience_level" in sql
