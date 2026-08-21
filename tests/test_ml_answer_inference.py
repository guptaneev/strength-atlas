from __future__ import annotations

import io
import json

from atlas.ml.answer_inference import HttpAnswerModel


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def _model() -> HttpAnswerModel:
    return HttpAnswerModel(
        url="https://model.invalid/generate",
        model_version="dpo-v1",
        artifact_sha256="abc123",
        timeout_seconds=1,
    )


def test_answer_model_accepts_matching_version_checksum_and_citations(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.ml.answer_inference.urlopen",
        lambda *_args, **_kwargs: _Response({"answer": "Use this approach. [e1]", "model_version": "dpo-v1", "artifact_sha256": "abc123"}),
    )
    outcome = _model().generate(query="q", evidence=[{"evidence_id": "e1", "text": "x"}])
    assert outcome.mode == "answer_model"
    assert outcome.answer == "Use this approach. [e1]"


def test_answer_model_falls_back_on_unknown_citation(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.ml.answer_inference.urlopen",
        lambda *_args, **_kwargs: _Response({"answer": "Unsupported. [e9]", "model_version": "dpo-v1", "artifact_sha256": "abc123"}),
    )
    outcome = _model().generate(query="q", evidence=[{"evidence_id": "e1", "text": "x"}])
    assert outcome.answer is None
    assert outcome.fallback_reason == "citation_contract_violation"


def test_answer_model_falls_back_on_checksum_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.ml.answer_inference.urlopen",
        lambda *_args, **_kwargs: _Response({"answer": "Supported. [e1]", "model_version": "dpo-v1", "artifact_sha256": "wrong"}),
    )
    outcome = _model().generate(query="q", evidence=[{"evidence_id": "e1", "text": "x"}])
    assert outcome.fallback_reason == "artifact_checksum_mismatch"
