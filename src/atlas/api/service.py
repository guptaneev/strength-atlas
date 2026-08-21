from __future__ import annotations

from collections import Counter
from datetime import datetime, UTC
import logging
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.api.schemas import (
    DashboardSummary,
    ProgramSearchItem,
    RetrievalDebugResponse,
    RetrievalDebugSummary,
    RetrievalEvidenceSelection,
    RetrievalProgramCandidate,
    RetrievalStatusResponse,
    RetrievalSourceCandidate,
    SourceDetailCrawl,
    SourceDetailDocument,
    SourceDetailProgram,
    SourceDetailResponse,
    SourceListItem,
    SourceSearchItem,
)
from atlas.api.traces import append_retrieval_trace
from atlas.ask.contracts import AskAnswerRequest, AskAtlasResponse, EvidenceCard, RetrievalRequest
from atlas.config.settings import get_settings
from atlas.db.models import Claim, CrawlJob, Document, Domain, Program, Source
from atlas.search.programs import ProgramSearchFilters, search_programs
from atlas.search.sources import search_sources
from atlas.ml.inference import (
    RerankerRuntime,
    build_program_candidates,
    build_source_candidates,
    get_reranker_runtime,
    rerank_items_safely,
)
from atlas.ml.answer_inference import HttpAnswerModel

logger = logging.getLogger("atlas.retrieval")


def run_source_search(
    session: Session,
    *,
    query: str,
    domain: str | None,
    limit: int,
) -> list[SourceSearchItem]:
    rows = search_sources(session, query=query, domain=domain, limit=limit)
    output: list[SourceSearchItem] = []
    for row in rows:
        document = session.get(Document, row.latest_document_id) if row.latest_document_id else None
        domain_row = session.get(Domain, row.domain_id) if row.domain_id else None
        output.append(SourceSearchItem(
            id=row.id,
            canonical_url=row.canonical_url,
            status=row.status,
            last_crawled_at=row.last_crawled_at.isoformat() if row.last_crawled_at else None,
            title=row.title,
            domain=domain_row.domain if domain_row else None,
            excerpt=_extract_snippet(document.raw_text if document else None, query),
            published_at=document.published_at.isoformat() if document and document.published_at else None,
            confidence=document.parse_confidence if document else None,
        ))
    return output


def run_source_list(
    session: Session,
    *,
    domain: str | None,
    status: str | None,
    limit: int,
) -> list[SourceListItem]:
    query = select(Source, Domain.domain).join(Domain, Domain.id == Source.domain_id).order_by(Source.id.asc())
    if domain:
        query = query.where(Domain.domain == domain.lower())
    if status:
        query = query.where(Source.status == status)
    rows = session.execute(query.limit(limit)).all()
    return [
        SourceListItem(
            id=src.id,
            canonical_url=src.canonical_url,
            status=src.status,
            last_crawled_at=src.last_crawled_at.isoformat() if src.last_crawled_at else None,
            domain=domain_name,
            title=src.title,
        )
        for src, domain_name in rows
    ]


def run_source_detail(session: Session, *, source_id: int) -> SourceDetailResponse | None:
    row = session.execute(
        select(Source, Domain.domain).join(Domain, Domain.id == Source.domain_id).where(Source.id == source_id)
    ).one_or_none()
    if row is None:
        return None
    source, domain_name = row

    document = session.get(Document, source.latest_document_id) if source.latest_document_id else None
    programs: list[Program] = []
    latest_crawl: CrawlJob | None = None
    if document is not None:
        programs = session.execute(
            select(Program).where(Program.document_id == document.id).order_by(Program.id.asc())
        ).scalars().all()
        if document.crawl_job_id:
            latest_crawl = session.get(CrawlJob, document.crawl_job_id)
    if latest_crawl is None:
        latest_crawl = session.execute(
            select(CrawlJob)
            .where(CrawlJob.source_id == source.id)
            .order_by(CrawlJob.started_at.desc(), CrawlJob.id.desc())
            .limit(1)
        ).scalar_one_or_none()

    return SourceDetailResponse(
        id=source.id,
        domain=domain_name,
        canonical_url=source.canonical_url,
        source_type=source.source_type,
        title=source.title,
        author=source.author,
        status=source.status,
        last_crawled_at=source.last_crawled_at.isoformat() if source.last_crawled_at else None,
        document=(
            SourceDetailDocument(
                id=document.id,
            )
            if document
            else None
        ),
        latest_crawl=(
            SourceDetailCrawl(
                id=latest_crawl.id,
                status=latest_crawl.status,
                retry_count=latest_crawl.retry_count,
                started_at=latest_crawl.started_at.isoformat() if latest_crawl.started_at else None,
                completed_at=latest_crawl.completed_at.isoformat() if latest_crawl.completed_at else None,
            )
            if latest_crawl
            else None
        ),
        programs=[
            SourceDetailProgram(id=program.id, name=program.name, confidence=program.confidence)
            for program in programs
        ],
    )


def run_dashboard_summary(session: Session) -> DashboardSummary:
    domains_total = int(session.execute(select(func.count(Domain.id))).scalar_one() or 0)
    allowlisted_domains = int(
        session.execute(select(func.count(Domain.id)).where(Domain.allowlisted.is_(True))).scalar_one() or 0
    )
    paused_domains = int(
        session.execute(select(func.count(Domain.id)).where(Domain.paused.is_(True))).scalar_one() or 0
    )

    sources_total = int(session.execute(select(func.count(Source.id))).scalar_one() or 0)
    sources_pending = int(
        session.execute(select(func.count(Source.id)).where(Source.status == "pending")).scalar_one() or 0
    )
    sources_succeeded = int(
        session.execute(select(func.count(Source.id)).where(Source.status == "succeeded")).scalar_one() or 0
    )
    sources_failed = int(
        session.execute(select(func.count(Source.id)).where(Source.status == "failed")).scalar_one() or 0
    )

    documents_total = int(session.execute(select(func.count(Document.id))).scalar_one() or 0)
    programs_total = int(session.execute(select(func.count(Program.id))).scalar_one() or 0)
    claims_total = int(session.execute(select(func.count(Claim.id))).scalar_one() or 0)

    latest_successful_crawl_at = session.execute(
        select(func.max(CrawlJob.started_at)).where(CrawlJob.status == "succeeded")
    ).scalar_one_or_none()
    recent_crawls = session.execute(
        select(CrawlJob.status).order_by(CrawlJob.started_at.desc(), CrawlJob.id.desc()).limit(20)
    ).scalars().all()
    recent_crawls_failed = len([status for status in recent_crawls if status == "failed"])

    return DashboardSummary(
        domains_total=domains_total,
        allowlisted_domains=allowlisted_domains,
        paused_domains=paused_domains,
        sources_total=sources_total,
        sources_pending=sources_pending,
        sources_succeeded=sources_succeeded,
        sources_failed=sources_failed,
        documents_total=documents_total,
        programs_total=programs_total,
        claims_total=claims_total,
        latest_successful_crawl_at=(
            latest_successful_crawl_at.isoformat() if latest_successful_crawl_at else None
        ),
        recent_crawls_analyzed=len(recent_crawls),
        recent_crawls_failed=recent_crawls_failed,
    )


def run_program_search(
    session: Session,
    *,
    query: str,
    filters: ProgramSearchFilters,
    limit: int,
    apply_reranking: bool = True,
) -> list[ProgramSearchItem]:
    settings = get_settings()
    runtime = _configured_reranker(settings) if apply_reranking and query.strip() else None
    candidate_depth = max(limit, int(getattr(settings, "reranker_candidate_depth", 50))) if runtime else limit
    rows = search_programs(session, query or None, filters, limit=candidate_depth)
    output: list[ProgramSearchItem] = []
    for row in rows:
        doc = session.get(Document, row.document_id)
        source = session.get(Source, doc.source_id) if doc else None
        domain_row = session.get(Domain, source.domain_id) if source else None
        output.append(
            ProgramSearchItem(
                id=row.id,
                name=row.name,
                confidence=row.confidence,
                document_id=row.document_id,
                source_id=doc.source_id if doc else None,
                canonical_url=source.canonical_url if source else None,
                coach_name=row.coach_name,
                days_per_week=row.days_per_week,
                specialization=row.specialization,
                experience_level=row.experience_level,
                progression_type=row.progression_type,
                split_type=row.split_type,
                summary=row.summary,
                source_title=source.title if source else None,
                source_domain=domain_row.domain if domain_row else None,
            )
        )
    outcome = rerank_items_safely(
        query=query,
        items=output,
        candidates=build_program_candidates(session, output),
        runtime=runtime,
    )
    logger.info(
        "program_search retrieval_mode=%s result_count=%s model_version=%s fallback_reason=%s",
        outcome.mode,
        min(len(outcome.items), limit),
        outcome.model_version or "none",
        outcome.fallback_reason or "none",
    )
    return outcome.items[:limit]


def run_retrieval_status() -> RetrievalStatusResponse:
    runtime = _configured_reranker(get_settings())
    if runtime is None:
        return RetrievalStatusResponse(mode="baseline")
    return RetrievalStatusResponse(
        mode="reranked" if runtime.is_loaded else "configured",
        model_version=runtime.model_version,
        model_loaded=runtime.is_loaded,
        last_reranker_latency_ms=runtime.last_latency_ms,
        last_reranker_candidate_count=runtime.last_candidate_count or None,
    )


def run_retrieval(
    session: Session,
    request: RetrievalRequest,
) -> AskAtlasResponse:
    debug = run_retrieval_debug(session, request)
    return debug.ask_response


def run_retrieval_debug(
    session: Session,
    request: RetrievalRequest,
) -> RetrievalDebugResponse:
    settings = get_settings()
    reranker = _configured_reranker(settings)
    candidate_depth = getattr(settings, "reranker_candidate_depth", 50)
    source_depth = max(request.max_sources, candidate_depth) if reranker else request.max_sources
    program_depth = max(request.max_programs, candidate_depth) if reranker else request.max_programs
    source_results = run_source_search(
        session,
        query=request.query,
        domain=request.filters.domain,
        limit=source_depth,
    )
    program_results = run_program_search(
        session,
        query=request.query,
        filters=ProgramSearchFilters(
            days_per_week=request.filters.days_per_week,
            specialization=request.filters.specialization,
            experience_level=request.filters.experience_level,
            progression_type=request.filters.progression_type,
            split_type=request.filters.split_type,
            domain=request.filters.domain,
        ),
        limit=program_depth,
        apply_reranking=False,
    )
    retrieval_mode = "baseline"
    model_version = None
    fallback_reason = None
    source_latency_ms = None
    program_latency_ms = None
    if reranker is not None:
        source_outcome = rerank_items_safely(
            query=request.query,
            items=source_results,
            candidates=build_source_candidates(session, source_results),
            runtime=reranker,
        )
        program_outcome = rerank_items_safely(
            query=request.query,
            items=program_results,
            candidates=build_program_candidates(session, program_results),
            runtime=reranker,
        )
        source_results = source_outcome.items[: request.max_sources]
        program_results = program_outcome.items[: request.max_programs]
        modes = {source_outcome.mode, program_outcome.mode}
        retrieval_mode = modes.pop() if len(modes) == 1 else "mixed_fallback"
        model_version = reranker.model_version
        fallback_reason = source_outcome.fallback_reason or program_outcome.fallback_reason
        source_latency_ms = source_outcome.latency_ms
        program_latency_ms = program_outcome.latency_ms
    logger.info(
        "ask_retrieval retrieval_mode=%s source_count=%s program_count=%s model_version=%s fallback_reason=%s",
        retrieval_mode,
        len(source_results),
        len(program_results),
        model_version or "none",
        fallback_reason or "none",
    )

    evidence: list[EvidenceCard] = []
    evidence_debug: list[RetrievalEvidenceSelection] = []
    seen_pairs: set[tuple[int, int]] = set()

    program_evidence_limit = max(1, request.max_sources // 2)
    for item in program_results[:program_evidence_limit]:
        if item.source_id is None:
            continue
        pair = (item.source_id, item.document_id)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        source = session.get(Source, item.source_id)
        document = session.get(Document, item.document_id)
        snippet = _extract_snippet(document.raw_text if document else None, request.query)
        evidence.append(
            EvidenceCard(
                source_id=item.source_id,
                document_id=item.document_id,
                canonical_url=item.canonical_url or "",
                title=item.name,
                snippet=snippet,
                parse_confidence=item.confidence,
                last_crawled_at=source.last_crawled_at.isoformat() if source and source.last_crawled_at else None,
                domain=_domain_from_url(item.canonical_url or ""),
                source_title=source.title if source else None,
                published_at=document.published_at.isoformat() if document and document.published_at else None,
            )
        )
        evidence_debug.append(
            RetrievalEvidenceSelection(
                source_id=item.source_id,
                document_id=item.document_id,
                canonical_url=item.canonical_url or "",
                title=item.name,
                parse_confidence=item.confidence,
                reason="program_match",
            )
        )

    if len(evidence) < request.max_sources:
        for src in source_results:
            source_row = session.get(Source, src.id)
            doc_id = int(source_row.latest_document_id) if source_row and source_row.latest_document_id else 0
            if (src.id, doc_id) in seen_pairs:
                continue
            document = session.get(Document, doc_id) if doc_id else None
            snippet = _extract_snippet(document.raw_text if document else None, request.query)
            evidence.append(
                EvidenceCard(
                    source_id=src.id,
                    document_id=doc_id,
                    canonical_url=src.canonical_url,
                    title=src.title or (source_row.title if source_row else None),
                    snippet=snippet,
                    parse_confidence=src.confidence,
                    last_crawled_at=src.last_crawled_at,
                    domain=src.domain or _domain_from_url(src.canonical_url),
                    source_title=src.title or (source_row.title if source_row else None),
                    published_at=src.published_at,
                )
            )
            evidence_debug.append(
                RetrievalEvidenceSelection(
                    source_id=src.id,
                    document_id=doc_id,
                    canonical_url=src.canonical_url,
                    title=src.title,
                    parse_confidence=src.confidence,
                    reason="source_fallback",
                )
            )
            if len(evidence) >= request.max_sources:
                break

    if not evidence:
        ask_response = AskAtlasResponse(
            answer="Insufficient evidence in indexed corpus for this query.",
            confidence=0.0,
            evidence=[],
            status="insufficient_evidence",
        )
        debug_response = _build_debug_response(
            request=request,
            source_results=source_results,
            program_results=program_results,
            evidence=evidence_debug,
            ask_response=ask_response,
            retrieval_mode=retrieval_mode,
            reranker_model_version=model_version,
            reranker_fallback_reason=fallback_reason,
            reranker_source_latency_ms=source_latency_ms,
            reranker_program_latency_ms=program_latency_ms,
        )
        _persist_retrieval_debug_trace(debug_response)
        return debug_response

    answer = (
        f"Retrieved {len(evidence)} evidence items for query '{request.query}'. "
        "Use evidence cards for grounded synthesis."
    )
    ask_response = AskAtlasResponse(
        answer=answer,
        confidence=None,
        evidence=evidence[: request.max_sources],
        status="ok",
    )
    debug_response = _build_debug_response(
        request=request,
        source_results=source_results,
        program_results=program_results,
        evidence=evidence_debug[: request.max_sources],
        ask_response=ask_response,
        retrieval_mode=retrieval_mode,
        reranker_model_version=model_version,
        reranker_fallback_reason=fallback_reason,
        reranker_source_latency_ms=source_latency_ms,
        reranker_program_latency_ms=program_latency_ms,
    )
    _persist_retrieval_debug_trace(debug_response)
    return debug_response


def run_answer(
    session: Session,
    request: AskAnswerRequest,
) -> AskAtlasResponse:
    debug = run_retrieval_debug(session, request)
    response = debug.ask_response
    if response.status != "ok" or not response.evidence:
        return response

    evidence = response.evidence[: request.max_evidence]
    domain_counts = Counter(_domain_from_url(item.canonical_url) for item in evidence if item.canonical_url)
    top_domains = [name for name, _count in domain_counts.most_common(3)]
    named_evidence = [item.title for item in evidence if item.title][:5]
    snippets = [item.snippet for item in evidence if item.snippet][:3]
    avg_conf = _avg([item.parse_confidence for item in evidence if item.parse_confidence is not None])

    lines: list[str] = []
    lines.append(f"For '{request.query}', here are the strongest grounded takeaways from the indexed coaching corpus.")
    lines.append(f"Found {len(evidence)} grounded evidence items.")
    if named_evidence:
        lines.append("Most relevant programs and sources: " + ", ".join(named_evidence) + ".")
    if snippets:
        lines.append("Key practical cues from source text:")
        for snippet in snippets:
            lines.append(f"- {snippet}")
    if top_domains:
        lines.append("Strongest supporting domains: " + ", ".join(top_domains) + ".")
    if avg_conf is not None and avg_conf < 0.65:
        lines.append("Evidence quality is limited, so treat these findings as directional rather than conclusive.")
    elif len(evidence) < 2:
        lines.append("Only one supporting source was found, so this answer carries meaningful uncertainty.")
    lines.append("Use evidence cards below for transparent source-level verification.")

    deterministic_answer = " ".join(lines)
    answer = deterministic_answer
    answer_mode = "deterministic"
    answer_model_version = None
    answer_fallback_reason = None
    settings = get_settings()
    if settings.answer_model_enabled:
        if not settings.answer_model_url:
            answer_mode = "deterministic_fallback"
            answer_model_version = settings.answer_model_version
            answer_fallback_reason = "missing_model_url"
        else:
            model = HttpAnswerModel(
                url=settings.answer_model_url,
                model_version=settings.answer_model_version,
                artifact_sha256=settings.answer_model_artifact_sha256,
                api_key=settings.answer_model_api_key,
                timeout_seconds=settings.answer_model_timeout_seconds,
            )
            model_evidence = [
                {
                    "evidence_id": f"e{index}",
                    "title": item.title,
                    "text": item.snippet or "",
                    "canonical_url": item.canonical_url,
                }
                for index, item in enumerate(evidence, start=1)
            ]
            outcome = model.generate(query=request.query, evidence=model_evidence)
            answer_model_version = outcome.model_version
            answer_mode = outcome.mode
            answer_fallback_reason = outcome.fallback_reason
            if outcome.answer is not None:
                answer = outcome.answer
    logger.info(
        "ask_answer answer_mode=%s model_version=%s fallback_reason=%s",
        answer_mode,
        answer_model_version or "none",
        answer_fallback_reason or "none",
    )

    return AskAtlasResponse(
        answer=answer,
        confidence=avg_conf,
        evidence=evidence if request.include_evidence else [],
        status="ok",
        answer_mode=answer_mode,
        answer_model_version=answer_model_version,
        answer_fallback_reason=answer_fallback_reason,
    )


def _build_debug_response(
    *,
    request: RetrievalRequest,
    source_results: list[SourceSearchItem],
    program_results: list[ProgramSearchItem],
    evidence: list[RetrievalEvidenceSelection],
    ask_response: AskAtlasResponse,
    retrieval_mode: str = "baseline",
    reranker_model_version: str | None = None,
    reranker_fallback_reason: str | None = None,
    reranker_source_latency_ms: float | None = None,
    reranker_program_latency_ms: float | None = None,
) -> RetrievalDebugResponse:
    source_candidates = [
        RetrievalSourceCandidate(
            rank=index + 1,
            id=row.id,
            canonical_url=row.canonical_url,
            status=row.status,
            last_crawled_at=row.last_crawled_at,
        )
        for index, row in enumerate(source_results)
    ]
    program_candidates = [
        RetrievalProgramCandidate(
            rank=index + 1,
            id=row.id,
            name=row.name,
            confidence=row.confidence,
            document_id=row.document_id,
            source_id=row.source_id,
            canonical_url=row.canonical_url,
        )
        for index, row in enumerate(program_results)
    ]
    return RetrievalDebugResponse(
        request_query=request.query,
        filters=request.filters.model_dump(),
        source_candidates=source_candidates,
        program_candidates=program_candidates,
        evidence=evidence,
        summary=RetrievalDebugSummary(
            source_candidates=len(source_candidates),
            program_candidates=len(program_candidates),
            evidence_selected=len(evidence),
            retrieval_mode=retrieval_mode,
            reranker_model_version=reranker_model_version,
            reranker_fallback_reason=reranker_fallback_reason,
            reranker_source_latency_ms=reranker_source_latency_ms,
            reranker_program_latency_ms=reranker_program_latency_ms,
        ),
        ask_response=ask_response,
    )


def _persist_retrieval_debug_trace(debug_response: RetrievalDebugResponse) -> None:
    try:
        settings = get_settings()
        append_retrieval_trace(
            settings.retrieval_debug_trace_path,
            {
                "recorded_at": datetime.now(UTC).isoformat(),
                **debug_response.model_dump(),
            },
        )
    except Exception:
        # Trace persistence should not block retrieval APIs.
        return


def _domain_from_url(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).netloc.lower() or "unknown"


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _extract_snippet(raw_text: str | None, query: str, max_chars: int = 220) -> str | None:
    if not raw_text:
        return None
    compact = " ".join(raw_text.split())
    if not compact:
        return None
    query_terms = [term for term in re.findall(r"[a-z0-9]+", query.lower()) if len(term) > 2]
    if not query_terms:
        snippet = compact[:max_chars]
        return snippet + ("..." if len(compact) > max_chars else "")

    lower = compact.lower()
    idx = min((lower.find(term) for term in query_terms if lower.find(term) >= 0), default=-1)
    if idx < 0:
        snippet = compact[:max_chars]
        return snippet + ("..." if len(compact) > max_chars else "")

    start = max(0, idx - 70)
    end = min(len(compact), start + max_chars)
    snippet = compact[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(compact):
        snippet = snippet + "..."
    return snippet


def _configured_reranker(settings) -> RerankerRuntime | None:
    model_path = str(getattr(settings, "reranker_model_path", None) or "").strip()
    if not model_path:
        return None
    return get_reranker_runtime(
        model_path,
        int(getattr(settings, "reranker_max_length", 256)),
        int(getattr(settings, "reranker_batch_size", 16)),
        float(getattr(settings, "reranker_timeout_seconds", 8.0)),
        int(getattr(settings, "reranker_max_workers", 1)),
        int(getattr(settings, "reranker_failure_cooldown_seconds", 60)),
        str(getattr(settings, "reranker_model_version", "strength-atlas-cross-encoder-authoritative-v1")),
        getattr(settings, "reranker_weights_sha256", None),
    )
