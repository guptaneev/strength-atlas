"""Typed, fail-open inference helpers shared by search and Ask Atlas."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import logging
from pathlib import Path
import threading
import time
from typing import Generic, Sequence, TypeVar

from sqlalchemy.orm import Session

from atlas.api.schemas import ProgramSearchItem, SourceSearchItem
from atlas.db.models import Document, Program, Source
from atlas.ml.documents import evidence_document_text, program_document_text
from atlas.ml.reranker import FineTunedCrossEncoder, RerankCandidate, Reranker, rerank_candidates

T = TypeVar("T")
logger = logging.getLogger("atlas.retrieval")


@lru_cache(maxsize=2)
def load_reranker(model_path: str, max_length: int, batch_size: int) -> FineTunedCrossEncoder:
    return FineTunedCrossEncoder(model_path, max_length=max_length, batch_size=batch_size)


@dataclass(frozen=True)
class RerankOutcome(Generic[T]):
    """A ranking result plus internal observability metadata."""

    items: list[T]
    mode: str
    model_version: str | None = None
    fallback_reason: str | None = None


class RerankerRuntime:
    """Own one lazily loaded model and run inference on bounded worker threads."""

    def __init__(
        self,
        model_path: str,
        *,
        max_length: int,
        batch_size: int,
        timeout_seconds: float,
        max_workers: int,
        failure_cooldown_seconds: int,
        model_version: str,
        weights_sha256: str | None,
    ) -> None:
        self.model_path = model_path
        self.max_length = max_length
        self.batch_size = batch_size
        self.timeout_seconds = timeout_seconds
        self.failure_cooldown_seconds = failure_cooldown_seconds
        self.model_version = model_version
        self.weights_sha256 = weights_sha256.lower().strip() if weights_sha256 else None
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="atlas-reranker")
        self._capacity = threading.BoundedSemaphore(max_workers)
        self._model: FineTunedCrossEncoder | None = None
        self._model_lock = threading.Lock()
        self._last_failure_at = 0.0
        self._last_failure_reason: str | None = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def rerank(self, query: str, candidates: Sequence[RerankCandidate]) -> tuple[list[RerankCandidate], str | None]:
        if not candidates:
            return [], None
        if self._cooldown_active():
            return list(candidates), self._last_failure_reason or "cooldown"
        if not self._capacity.acquire(blocking=False):
            logger.warning("reranker_fallback reason=busy model_version=%s", self.model_version)
            return list(candidates), "busy"

        future = self._executor.submit(self._load_and_rerank, query, tuple(candidates))
        future.add_done_callback(lambda _future: self._capacity.release())
        try:
            ranked = future.result(timeout=self.timeout_seconds)
        except FutureTimeoutError:
            self._record_failure("timeout")
            logger.warning(
                "reranker_fallback reason=timeout timeout_seconds=%s model_version=%s",
                self.timeout_seconds,
                self.model_version,
            )
            return list(candidates), "timeout"
        except Exception as exc:  # noqa: BLE001
            reason = _safe_failure_reason(exc)
            self._record_failure(reason)
            logger.warning(
                "reranker_fallback reason=%s error_type=%s model_version=%s",
                reason,
                exc.__class__.__name__,
                self.model_version,
            )
            return list(candidates), reason

        self._last_failure_at = 0.0
        self._last_failure_reason = None
        return ranked, None

    def _load_and_rerank(self, query: str, candidates: Sequence[RerankCandidate]) -> list[RerankCandidate]:
        model = self._get_model()
        return rerank_candidates(model, query, candidates)

    def _get_model(self) -> FineTunedCrossEncoder:
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is None:
                _validate_model_artifact(self.model_path, self.weights_sha256)
                self._model = load_reranker(self.model_path, self.max_length, self.batch_size)
                logger.info(
                    "reranker_loaded model_version=%s model_path_name=%s",
                    self.model_version,
                    Path(self.model_path).name,
                )
        return self._model

    def _cooldown_active(self) -> bool:
        if not self._last_failure_at or self.failure_cooldown_seconds <= 0:
            return False
        return (time.monotonic() - self._last_failure_at) < self.failure_cooldown_seconds

    def _record_failure(self, reason: str) -> None:
        self._last_failure_at = time.monotonic()
        self._last_failure_reason = reason


@lru_cache(maxsize=4)
def get_reranker_runtime(
    model_path: str,
    max_length: int,
    batch_size: int,
    timeout_seconds: float,
    max_workers: int,
    failure_cooldown_seconds: int,
    model_version: str,
    weights_sha256: str | None,
) -> RerankerRuntime:
    return RerankerRuntime(
        model_path,
        max_length=max_length,
        batch_size=batch_size,
        timeout_seconds=timeout_seconds,
        max_workers=max_workers,
        failure_cooldown_seconds=failure_cooldown_seconds,
        model_version=model_version,
        weights_sha256=weights_sha256,
    )


def rerank_items_safely(
    *,
    query: str,
    items: Sequence[T],
    candidates: Sequence[RerankCandidate],
    runtime: RerankerRuntime | None,
) -> RerankOutcome[T]:
    baseline = list(items)
    if runtime is None:
        return RerankOutcome(items=baseline, mode="baseline")

    by_id = {candidate.candidate_id: item for candidate, item in zip(candidates, items, strict=True)}
    ranked, fallback_reason = runtime.rerank(query, candidates)
    if fallback_reason:
        return RerankOutcome(
            items=baseline,
            mode="baseline_fallback",
            model_version=runtime.model_version,
            fallback_reason=fallback_reason,
        )
    return RerankOutcome(
        items=[by_id[candidate.candidate_id] for candidate in ranked],
        mode="reranked",
        model_version=runtime.model_version,
    )


def _validate_model_artifact(model_path: str, weights_sha256: str | None) -> None:
    root = Path(model_path)
    if not root.is_dir():
        raise FileNotFoundError("model_artifact_missing")
    for required in ("config.json", "model.safetensors", "tokenizer_config.json"):
        if not (root / required).is_file():
            raise ValueError("model_artifact_malformed")
    if weights_sha256:
        actual = _sha256(root / "model.safetensors")
        if actual != weights_sha256:
            raise ValueError("model_checksum_mismatch")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_failure_reason(exc: Exception) -> str:
    message = str(exc)
    if message in {"model_artifact_missing", "model_artifact_malformed", "model_checksum_mismatch"}:
        return message
    if isinstance(exc, FileNotFoundError):
        return "model_artifact_missing"
    if isinstance(exc, (ValueError, OSError)):
        return "model_incompatible"
    return "inference_error"


def rerank_program_items(
    session: Session,
    query: str,
    items: Sequence[ProgramSearchItem],
    reranker: Reranker,
) -> list[ProgramSearchItem]:
    candidates = build_program_candidates(session, items)
    by_id = {item.id: item for item in items}
    return [by_id[candidate.candidate_id] for candidate in rerank_candidates(reranker, query, candidates)]


def rerank_source_items(
    session: Session,
    query: str,
    items: Sequence[SourceSearchItem],
    reranker: Reranker,
) -> list[SourceSearchItem]:
    candidates = build_source_candidates(session, items)
    by_id = {item.id: item for item in items}
    return [by_id[candidate.candidate_id] for candidate in rerank_candidates(reranker, query, candidates)]


def build_program_candidates(
    session: Session,
    items: Sequence[ProgramSearchItem],
) -> list[RerankCandidate]:
    candidates: list[RerankCandidate] = []
    for item in items:
        program = session.get(Program, item.id)
        document = session.get(Document, item.document_id)
        source = session.get(Source, item.source_id) if item.source_id is not None else None
        text = (
            program_document_text(program, document, source)
            if program is not None
            else " | ".join(str(value) for value in item.model_dump().values() if value not in (None, ""))
        )
        candidates.append(RerankCandidate(item.id, text, "program"))
    return candidates


def build_source_candidates(
    session: Session,
    items: Sequence[SourceSearchItem],
) -> list[RerankCandidate]:
    candidates: list[RerankCandidate] = []
    for item in items:
        source = session.get(Source, item.id)
        document = session.get(Document, source.latest_document_id) if source and source.latest_document_id else None
        text = (
            evidence_document_text(document, source)
            if source is not None
            else " | ".join(str(value) for value in item.model_dump().values() if value not in (None, ""))
        )
        candidates.append(RerankCandidate(item.id, text, "source_evidence"))
    return candidates
