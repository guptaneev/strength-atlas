from atlas.api import service
from atlas.api.schemas import RetrievalDebugResponse
from atlas.ask.contracts import AskAnswerRequest


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
