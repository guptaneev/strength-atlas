from atlas.api import service
from atlas.api.schemas import RetrievalDebugResponse, SourceSearchItem
from atlas.ask.contracts import AskAnswerRequest, RetrievalRequest
from atlas.db.models import Document, Domain, Program, Source
from atlas.search.programs import ProgramSearchFilters
from atlas.ml.answer_inference import AnswerModelOutcome


def _debug_payload() -> RetrievalDebugResponse:
    return RetrievalDebugResponse.model_validate(
        {
            "request_query": "bench frequency",
            "filters": {"domain": "example.com"},
            "source_candidates": [],
            "program_candidates": [],
            "evidence": [
                {
                    "source_id": 1,
                    "document_id": 10,
                    "canonical_url": "https://example.com/a",
                    "title": "Program A",
                    "parse_confidence": 0.8,
                    "reason": "program_match",
                },
                {
                    "source_id": 2,
                    "document_id": 11,
                    "canonical_url": "https://example.com/b",
                    "title": "Program B",
                    "parse_confidence": 0.6,
                    "reason": "program_match",
                },
            ],
            "summary": {"source_candidates": 0, "program_candidates": 0, "evidence_selected": 2},
            "ask_response": {
                "answer": "Retrieved evidence.",
                "status": "ok",
                "evidence": [
                    {
                        "source_id": 1,
                        "document_id": 10,
                        "canonical_url": "https://example.com/a",
                        "title": "Program A",
                        "parse_confidence": 0.8,
                    },
                    {
                        "source_id": 2,
                        "document_id": 11,
                        "canonical_url": "https://example.com/b",
                        "title": "Program B",
                        "parse_confidence": 0.6,
                    },
                ],
            },
        }
    )


def test_run_answer_synthesizes_with_confidence(monkeypatch) -> None:
    monkeypatch.setattr(service, "run_retrieval_debug", lambda *_args, **_kwargs: _debug_payload())
    response = service.run_answer(
        session=object(),  # not used due monkeypatch
        request=AskAnswerRequest(
            query="bench frequency",
            include_evidence=True,
            max_evidence=2,
            max_sources=5,
            max_programs=10,
        ),
    )
    assert response.status == "ok"
    assert response.confidence is not None
    assert "Found 2 grounded evidence items." in response.answer
    assert len(response.evidence) == 2


def test_run_answer_can_hide_evidence(monkeypatch) -> None:
    monkeypatch.setattr(service, "run_retrieval_debug", lambda *_args, **_kwargs: _debug_payload())
    response = service.run_answer(
        session=object(),
        request=AskAnswerRequest(
            query="bench frequency",
            include_evidence=False,
            max_evidence=2,
            max_sources=5,
            max_programs=10,
        ),
    )
    assert response.status == "ok"
    assert response.evidence == []


def test_run_answer_uses_feature_flagged_model_and_records_version(monkeypatch) -> None:
    monkeypatch.setattr(service, "run_retrieval_debug", lambda *_args, **_kwargs: _debug_payload())
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: type(
            "_S",
            (),
            {
                "answer_model_enabled": True,
                "answer_model_url": "https://model.invalid/generate",
                "answer_model_version": "dpo-v1",
                "answer_model_artifact_sha256": "abc123",
                "answer_model_api_key": None,
                "answer_model_timeout_seconds": 1.0,
            },
        )(),
    )
    monkeypatch.setattr(
        service.HttpAnswerModel,
        "generate",
        lambda *_args, **_kwargs: AnswerModelOutcome(
            answer="Train three times weekly. [e1]",
            mode="answer_model",
            model_version="dpo-v1",
            artifact_sha256="abc123",
        ),
    )
    response = service.run_answer(session=object(), request=AskAnswerRequest(query="bench frequency"))
    assert response.answer == "Train three times weekly. [e1]"
    assert response.answer_mode == "answer_model"
    assert response.answer_model_version == "dpo-v1"


def test_run_answer_preserves_deterministic_response_on_model_failure(monkeypatch) -> None:
    monkeypatch.setattr(service, "run_retrieval_debug", lambda *_args, **_kwargs: _debug_payload())
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: type(
            "_S",
            (),
            {
                "answer_model_enabled": True,
                "answer_model_url": "https://model.invalid/generate",
                "answer_model_version": "dpo-v1",
                "answer_model_artifact_sha256": "abc123",
                "answer_model_api_key": None,
                "answer_model_timeout_seconds": 1.0,
            },
        )(),
    )
    monkeypatch.setattr(
        service.HttpAnswerModel,
        "generate",
        lambda *_args, **_kwargs: AnswerModelOutcome(
            answer=None,
            mode="deterministic_fallback",
            model_version="dpo-v1",
            artifact_sha256="abc123",
            fallback_reason="citation_contract_violation",
        ),
    )
    response = service.run_answer(session=object(), request=AskAnswerRequest(query="bench frequency"))
    assert "Found 2 grounded evidence items." in response.answer
    assert response.answer_mode == "deterministic_fallback"
    assert response.answer_fallback_reason == "citation_contract_violation"


def test_run_retrieval_debug_persists_trace(monkeypatch) -> None:
    class _Session:
        def get(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(service, "run_source_search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(service, "run_program_search", lambda *_args, **_kwargs: [])

    observed = {}

    def _append(path: str, payload: dict):
        observed["path"] = path
        observed["payload"] = payload

    monkeypatch.setattr(service, "append_retrieval_trace", _append)
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: type("_S", (), {"retrieval_debug_trace_path": "var/atlas/retrieval-debug.jsonl"})(),
    )

    response = service.run_retrieval_debug(
        _Session(),
        request=service.RetrievalRequest(query="bench", max_sources=3, max_programs=5),
    )
    assert response.ask_response.status == "insufficient_evidence"
    assert observed["path"].endswith("retrieval-debug.jsonl")


class _ReverseRuntime:
    model_version = "model-v1"
    is_loaded = True

    def rerank(self, _query, candidates):
        return list(reversed(candidates)), None


class _RowSession:
    def __init__(self, rows):
        self.rows = rows

    def get(self, model, row_id):
        return self.rows.get((model, row_id))


def test_program_search_uses_reranker_and_preserves_metadata(monkeypatch) -> None:
    domain = Domain(id=1, domain="example.com")
    source = Source(
        id=1,
        url="https://example.com/programs",
        canonical_url="https://example.com/programs",
        domain_id=1,
        title="Program Library",
    )
    document = Document(id=10, source_id=1, raw_text="training")
    first = Program(id=20, document_id=10, name="First", days_per_week=3)
    second = Program(
        id=21,
        document_id=10,
        name="Beginner Four Day",
        coach_name="Coach Example",
        days_per_week=4,
        specialization="powerlifting",
        experience_level="beginner",
        split_type="upper_lower",
        summary="Four-day powerlifting plan.",
    )
    session = _RowSession({
        (Domain, 1): domain,
        (Source, 1): source,
        (Document, 10): document,
        (Program, 20): first,
        (Program, 21): second,
    })
    monkeypatch.setattr(service, "search_programs", lambda *_args, **_kwargs: [first, second])
    monkeypatch.setattr(service, "_configured_reranker", lambda _settings: _ReverseRuntime())
    monkeypatch.setattr(service, "get_settings", lambda: type("_S", (), {"reranker_candidate_depth": 2})())

    results = service.run_program_search(
        session,
        query="beginner four day powerlifting",
        filters=ProgramSearchFilters(),
        limit=1,
    )
    assert [item.id for item in results] == [21]
    assert results[0].days_per_week == 4
    assert results[0].coach_name == "Coach Example"
    assert results[0].canonical_url == "https://example.com/programs"


def test_informational_ask_reranks_source_evidence(monkeypatch) -> None:
    first_source = Source(
        id=1,
        url="https://example.com/one",
        canonical_url="https://example.com/one",
        domain_id=1,
        title="General Training",
        latest_document_id=10,
    )
    second_source = Source(
        id=2,
        url="https://example.com/two",
        canonical_url="https://example.com/two",
        domain_id=1,
        title="Bench Frequency",
        latest_document_id=11,
    )
    session = _RowSession({
        (Source, 1): first_source,
        (Source, 2): second_source,
        (Document, 10): Document(id=10, source_id=1, raw_text="general training"),
        (Document, 11): Document(id=11, source_id=2, raw_text="bench frequency guidance"),
    })
    monkeypatch.setattr(service, "_configured_reranker", lambda _settings: _ReverseRuntime())
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: type("_S", (), {"reranker_candidate_depth": 2, "retrieval_debug_trace_path": "unused"})(),
    )
    monkeypatch.setattr(
        service,
        "run_source_search",
        lambda *_args, **_kwargs: [
            SourceSearchItem(id=1, canonical_url=first_source.canonical_url, title=first_source.title),
            SourceSearchItem(id=2, canonical_url=second_source.canonical_url, title=second_source.title),
        ],
    )
    monkeypatch.setattr(service, "run_program_search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(service, "append_retrieval_trace", lambda *_args, **_kwargs: None)

    response = service.run_retrieval_debug(
        session,
        RetrievalRequest(query="how often should I bench", max_sources=2, max_programs=1),
    )
    assert response.summary.retrieval_mode == "reranked"
    assert [item.source_id for item in response.ask_response.evidence] == [2, 1]
    assert response.ask_response.evidence[0].canonical_url == "https://example.com/two"
