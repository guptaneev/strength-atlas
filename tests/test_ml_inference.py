from atlas.api.schemas import ProgramSearchItem, SourceSearchItem
from atlas.db.models import Document, Program, Source
import hashlib
import threading
import time

from atlas.ml import inference
from atlas.ml.inference import RerankerRuntime, rerank_items_safely, rerank_program_items, rerank_source_items
from atlas.ml.reranker import RerankCandidate


class _KeywordReranker:
    def score(self, query, candidates):
        return [1.0 if query.lower() in candidate.text.lower() else 0.0 for candidate in candidates]


class _Session:
    def __init__(self, rows):
        self.rows = rows

    def get(self, model, row_id):
        return self.rows.get((model, row_id))


def test_reranks_program_items_without_losing_identifiers() -> None:
    source = Source(id=1, url="https://example.com", canonical_url="https://example.com", domain_id=1)
    document = Document(id=10, source_id=1, raw_text="training")
    advanced = Program(id=20, document_id=10, name="advanced plan")
    beginner = Program(id=21, document_id=10, name="beginner plan")
    session = _Session({(Source, 1): source, (Document, 10): document, (Program, 20): advanced, (Program, 21): beginner})
    items = [
        ProgramSearchItem(id=20, document_id=10, source_id=1),
        ProgramSearchItem(id=21, document_id=10, source_id=1),
    ]
    ranked = rerank_program_items(session, "beginner", items, _KeywordReranker())
    assert [item.id for item in ranked] == [21, 20]


def test_reranks_source_evidence_and_preserves_provenance() -> None:
    generic = Source(id=1, url="https://one.example", canonical_url="https://one.example", domain_id=1, latest_document_id=10)
    bench = Source(id=2, url="https://two.example", canonical_url="https://two.example", domain_id=1, latest_document_id=11)
    session = _Session({
        (Source, 1): generic,
        (Source, 2): bench,
        (Document, 10): Document(id=10, source_id=1, raw_text="general strength"),
        (Document, 11): Document(id=11, source_id=2, raw_text="bench frequency"),
    })
    items = [SourceSearchItem(id=1, canonical_url=generic.canonical_url), SourceSearchItem(id=2, canonical_url=bench.canonical_url)]
    ranked = rerank_source_items(session, "bench", items, _KeywordReranker())
    assert [item.id for item in ranked] == [2, 1]
    assert ranked[0].canonical_url == "https://two.example"


def _model_artifact(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "tokenizer_config.json").write_text("{}", encoding="utf-8")
    weights = b"weights"
    (tmp_path / "model.safetensors").write_bytes(weights)
    return hashlib.sha256(weights).hexdigest()


def test_runtime_loads_model_once_and_preserves_complete_items(tmp_path, monkeypatch) -> None:
    checksum = _model_artifact(tmp_path)
    loads = []
    scoring_threads = []

    class _Model:
        def score(self, _query, candidates):
            scoring_threads.append(threading.get_ident())
            return [float(candidate.candidate_id) for candidate in candidates]

    def _load(*_args):
        loads.append(True)
        return _Model()

    monkeypatch.setattr(inference, "load_reranker", _load)
    runtime = RerankerRuntime(
        str(tmp_path),
        max_length=256,
        batch_size=8,
        timeout_seconds=1,
        max_workers=1,
        failure_cooldown_seconds=0,
        model_version="model-v1",
        weights_sha256=checksum,
    )
    items = ["first", "second"]
    candidates = [RerankCandidate(1, "one"), RerankCandidate(2, "two")]
    first = rerank_items_safely(query="q", items=items, candidates=candidates, runtime=runtime)
    second = rerank_items_safely(query="q", items=items, candidates=candidates, runtime=runtime)
    assert first.items == ["second", "first"]
    assert second.mode == "reranked"
    assert len(loads) == 1
    assert all(thread_id != threading.get_ident() for thread_id in scoring_threads)


def test_runtime_timeout_falls_back_to_baseline(tmp_path, monkeypatch) -> None:
    checksum = _model_artifact(tmp_path)

    class _SlowModel:
        def score(self, _query, candidates):
            time.sleep(0.1)
            return [0.0 for _candidate in candidates]

    monkeypatch.setattr(inference, "load_reranker", lambda *_args: _SlowModel())
    runtime = RerankerRuntime(
        str(tmp_path),
        max_length=256,
        batch_size=8,
        timeout_seconds=0.01,
        max_workers=1,
        failure_cooldown_seconds=0,
        model_version="model-v1",
        weights_sha256=checksum,
    )
    outcome = rerank_items_safely(
        query="q",
        items=["first", "second"],
        candidates=[RerankCandidate(1, "one"), RerankCandidate(2, "two")],
        runtime=runtime,
    )
    assert outcome.items == ["first", "second"]
    assert outcome.mode == "baseline_fallback"
    assert outcome.fallback_reason == "timeout"


def test_runtime_missing_and_corrupt_artifacts_fall_back(tmp_path) -> None:
    for path, checksum, reason in (
        (tmp_path / "missing", None, "model_artifact_missing"),
        (tmp_path / "corrupt", "0" * 64, "model_checksum_mismatch"),
    ):
        if path.name == "corrupt":
            _model_artifact(path)
        runtime = RerankerRuntime(
            str(path),
            max_length=256,
            batch_size=8,
            timeout_seconds=1,
            max_workers=1,
            failure_cooldown_seconds=0,
            model_version="model-v1",
            weights_sha256=checksum,
        )
        outcome = rerank_items_safely(
            query="q",
            items=["baseline"],
            candidates=[RerankCandidate(1, "one")],
            runtime=runtime,
        )
        assert outcome.items == ["baseline"]
        assert outcome.fallback_reason == reason


def test_runtime_incompatible_model_falls_back(tmp_path, monkeypatch) -> None:
    checksum = _model_artifact(tmp_path)
    monkeypatch.setattr(inference, "load_reranker", lambda *_args: (_ for _ in ()).throw(OSError("bad config")))
    runtime = RerankerRuntime(
        str(tmp_path),
        max_length=256,
        batch_size=8,
        timeout_seconds=1,
        max_workers=1,
        failure_cooldown_seconds=0,
        model_version="model-v1",
        weights_sha256=checksum,
    )
    outcome = rerank_items_safely(
        query="q",
        items=["baseline"],
        candidates=[RerankCandidate(1, "one")],
        runtime=runtime,
    )
    assert outcome.items == ["baseline"]
    assert outcome.fallback_reason == "model_incompatible"
