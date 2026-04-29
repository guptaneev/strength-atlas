from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from atlas.db.models import Document, Source
from atlas.search.programs import ProgramSearchFilters, search_programs
from atlas.search.sources import search_sources


@dataclass(frozen=True)
class SearchEvalQuery:
    name: str
    mode: str
    query: str
    top_k: int
    filters: dict[str, Any]
    must_include_canonical_urls: list[str]


def load_eval_suite(path: str) -> list[SearchEvalQuery]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    queries = raw.get("queries")
    if not isinstance(queries, list):
        raise ValueError("Invalid eval fixture: expected top-level 'queries' array")

    suite: list[SearchEvalQuery] = []
    for row in queries:
        if not isinstance(row, dict):
            continue
        suite.append(
            SearchEvalQuery(
                name=str(row.get("name") or "unnamed"),
                mode=str(row.get("mode") or "").strip().lower(),
                query=str(row.get("query") or ""),
                top_k=max(1, int(row.get("top_k", 10) or 10)),
                filters=row.get("filters", {}) if isinstance(row.get("filters"), dict) else {},
                must_include_canonical_urls=[
                    str(url) for url in row.get("must_include_canonical_urls", []) if isinstance(url, str)
                ],
            )
        )
    return suite


def run_search_eval_suite(session: Session, suite: list[SearchEvalQuery]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    passed = 0

    for test in suite:
        if test.mode == "programs":
            observed_urls = _evaluate_program_query(session, test)
        elif test.mode == "sources":
            observed_urls = _evaluate_source_query(session, test)
        else:
            observed_urls = []

        expected = test.must_include_canonical_urls
        missing = [url for url in expected if url not in observed_urls]
        ok = not missing and test.mode in {"programs", "sources"}
        if ok:
            passed += 1

        results.append(
            {
                "name": test.name,
                "mode": test.mode,
                "query": test.query,
                "top_k": test.top_k,
                "passed": ok,
                "expected_urls": expected,
                "observed_urls": observed_urls,
                "missing_urls": missing,
            }
        )

    total = len(results)
    return {
        "queries_total": total,
        "queries_passed": passed,
        "pass_rate": (passed / total) if total else 0.0,
        "results": results,
    }


def _evaluate_program_query(session: Session, test: SearchEvalQuery) -> list[str]:
    allowed_filter_keys = ProgramSearchFilters.__dataclass_fields__.keys()
    safe_filters = {k: v for k, v in test.filters.items() if k in allowed_filter_keys}
    filters = ProgramSearchFilters(**safe_filters)
    rows = search_programs(session, test.query or None, filters, limit=test.top_k)
    urls: list[str] = []
    for row in rows:
        doc = session.get(Document, row.document_id)
        source = session.get(Source, doc.source_id) if doc else None
        if source and source.canonical_url:
            urls.append(source.canonical_url)
    return urls


def _evaluate_source_query(session: Session, test: SearchEvalQuery) -> list[str]:
    rows = search_sources(
        session,
        query=test.query,
        domain=test.filters.get("domain"),
        limit=test.top_k,
    )
    return [row.canonical_url for row in rows if row.canonical_url]
