from __future__ import annotations

import datetime as dt
import html
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from atlas.browser_use.client import BrowserUseClient
from atlas.config.settings import get_settings
from atlas.db.models import Claim, CrawlJob, Document, Program, Source
from atlas.ingest.normalization import (
    build_content_tsv_text,
    normalize_extraction,
    validate_normalized_extraction,
)
from atlas.ingest.retries import is_retryable_browser_use_error
from atlas.storage.client import SupabaseStorageClient
from atlas.storage.paths import extracted_json_path, html_path


class ExtractValidationError(RuntimeError):
    pass


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


async def extract_url(
    session: Session,
    client: BrowserUseClient,
    url: str,
    source: Source | None = None,
    storage: SupabaseStorageClient | None = None,
) -> Document:
    if source is None:
        raise ValueError("Source is required for extract_url. Create/discover a source first.")

    crawl_job = CrawlJob(
        job_type="extract",
        source_id=source.id,
        target_url=url,
        status="pending",
        started_at=utcnow(),
    )
    session.add(crawl_job)
    session.commit()

    crawl_job.status = "running"
    session.commit()

    try:
        settings = get_settings()
        max_retries = max(0, settings.max_crawl_retries)
        total_attempts = max_retries + 1
        result = None
        normalized = None
        for attempt_index in range(total_attempts):
            model = _extract_model_for_attempt(settings, attempt_index)
            try:
                result = await _extract_with_optional_model(client, url, model)
                crawl_job.browser_use_session_id = result.session_id
                crawl_job.browser_use_live_url = result.live_url
                crawl_job.browser_use_cost_usd = result.total_cost_usd

                normalized = normalize_extraction(result.output, url=url)
                errors = validate_normalized_extraction(normalized, url=url)
                if errors:
                    raise ExtractValidationError(", ".join(errors))
                break
            except Exception as exc:
                retryable = is_retryable_browser_use_error(exc) or isinstance(exc, ExtractValidationError)
                if attempt_index < max_retries and retryable:
                    crawl_job.retry_count = attempt_index + 1
                    crawl_job.error_message = (
                        f"extract attempt {attempt_index + 1}/{total_attempts} failed "
                        f"(model={model or 'default'}): {exc}; retrying"
                    )
                    crawl_job.status = "running"
                    session.commit()
                    continue
                crawl_job.retry_count = min(attempt_index, max_retries)
                raise
        if result is None or normalized is None:
            raise RuntimeError("extract produced no result")
        source.title = normalized.title
        source.author = normalized.author
        source.source_type = normalized.source_type

        source_id = source.id
        html_storage = html_path(source_id, crawl_job.id)
        extracted_storage = extracted_json_path(source_id, crawl_job.id)

        if storage:
            storage.upload_text(
                html_storage,
                _raw_html_from_extraction(normalized.structured_output, normalized.raw_text),
                "text/html; charset=utf-8",
            )
            storage.upload_json(extracted_storage, normalized.structured_output)

        document = Document(
            source_id=source_id,
            crawl_job_id=crawl_job.id,
            raw_text=normalized.raw_text,
            html_storage_path=html_storage,
            extracted_json_storage_path=extracted_storage,
            parse_confidence=normalized.parse_confidence,
            created_at=utcnow(),
        )
        content_text = build_content_tsv_text(normalized.title, normalized.summary, normalized.raw_text)
        document.content_tsv = func.to_tsvector("english", content_text)
        session.add(document)
        session.flush()

        inserted_programs: list[Program] = []
        for program in normalized.programs:
            row = Program(
                document_id=document.id,
                name=program.get("name"),
                coach_name=program.get("coach_name"),
                days_per_week=program.get("days_per_week"),
                specialization=program.get("specialization"),
                experience_level=program.get("experience_level"),
                progression_type=program.get("progression_type"),
                split_type=program.get("split_type"),
                summary=program.get("summary"),
                confidence=program.get("confidence"),
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            session.add(row)
            inserted_programs.append(row)
        session.flush()
        program_name_map = _build_program_name_map(inserted_programs)

        for claim in normalized.claims:
            mapped_program_id = _map_claim_program_id(
                claim.get("program_id"),
                inserted_programs,
                program_name_map=program_name_map,
            )
            session.add(
                Claim(
                    document_id=document.id,
                    program_id=mapped_program_id,
                    claim_type=claim.get("claim_type"),
                    raw_text=claim.get("raw_text"),
                    normalized_value=claim.get("normalized_value"),
                    confidence=claim.get("confidence"),
                    created_at=utcnow(),
                )
            )

        source.latest_document_id = document.id
        source.last_crawled_at = utcnow()
        source.status = "succeeded"

        crawl_job.status = "succeeded"
        crawl_job.error_message = None
        crawl_job.completed_at = utcnow()
        session.commit()
        return document
    except Exception as exc:
        if hasattr(session, "rollback"):
            session.rollback()
        crawl_job.status = "failed"
        settings = get_settings()
        total_attempts = max(0, settings.max_crawl_retries) + 1
        crawl_job.error_message = f"extract failed after {crawl_job.retry_count + 1}/{total_attempts} attempts: {exc}"
        crawl_job.completed_at = utcnow()
        session.commit()
        raise


def build_extraction_diagnostics(output: object, *, url: str | None = None) -> dict[str, Any]:
    normalized = normalize_extraction(output, url=url)
    errors = validate_normalized_extraction(normalized, url=url)
    return {
        "payload_type": normalized.payload_type,
        "parse_confidence": normalized.parse_confidence,
        "raw_text_length": len((normalized.raw_text or "").strip()),
        "programs_count": len(normalized.programs),
        "claims_count": len(normalized.claims),
        "warnings": normalized.warnings,
        "validation_errors": errors,
    }


async def _extract_with_optional_model(client: BrowserUseClient, url: str, model: str | None):
    try:
        return await client.extract_url(url, model=model)
    except TypeError as exc:
        # Backwards compatibility for test doubles that don't accept model.
        if "unexpected keyword argument" in str(exc) and "model" in str(exc):
            return await client.extract_url(url)
        raise


def _extract_model_for_attempt(settings: Any, attempt_index: int) -> str | None:
    primary = getattr(settings, "browser_use_extract_model_primary", "bu-mini")
    fallback = getattr(settings, "browser_use_extract_model_fallback", "bu-max")
    if attempt_index == 0:
        return primary
    return fallback or primary


def _raw_html_from_extraction(output: object, raw_text: str | None) -> str:
    if isinstance(output, dict):
        for key in ("raw_html", "html", "page_html"):
            value = output.get(key)
            if isinstance(value, str) and value.strip():
                return value
    body = html.escape(raw_text or "")
    return f"<html><body><pre>{body}</pre></body></html>"


def _map_claim_program_id(
    raw_program_id: object,
    inserted_programs: list[Program],
    *,
    program_name_map: dict[str, int],
) -> int | None:
    if raw_program_id is None or not inserted_programs:
        return None

    # Model payloads usually reference local program indexes (0-based or
    # occasionally 1-based), not real DB ids.
    try:
        numeric = int(raw_program_id)
    except (TypeError, ValueError):
        numeric = None

    if numeric is not None:
        # Prefer explicit 0-based index when valid.
        if 0 <= numeric < len(inserted_programs):
            program_id = inserted_programs[numeric].id
            if program_id is not None:
                return program_id
        # Fallback for 1-based index values.
        one_based_index = numeric - 1
        if 0 <= one_based_index < len(inserted_programs):
            program_id = inserted_programs[one_based_index].id
            if program_id is not None:
                return program_id
        return None

    if isinstance(raw_program_id, str):
        return program_name_map.get(raw_program_id.strip().lower())
    return None


def _build_program_name_map(inserted_programs: list[Program]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for row in inserted_programs:
        if row.id is None or not row.name:
            continue
        key = row.name.strip().lower()
        if key:
            mapping[key] = row.id
    return mapping
