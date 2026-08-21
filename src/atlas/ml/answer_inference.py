"""Feature-flagged answer-model inference with strict fallback boundaries."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from atlas.ml.answer_evaluation import extract_citations


@dataclass(frozen=True)
class AnswerModelOutcome:
    answer: str | None
    mode: str
    model_version: str | None
    artifact_sha256: str | None
    fallback_reason: str | None = None


class HttpAnswerModel:
    def __init__(
        self,
        *,
        url: str,
        model_version: str,
        timeout_seconds: float,
        api_key: str | None = None,
        artifact_sha256: str | None = None,
    ) -> None:
        self.url = url
        self.model_version = model_version
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key
        self.artifact_sha256 = artifact_sha256

    def generate(self, *, query: str, evidence: list[dict[str, Any]]) -> AnswerModelOutcome:
        payload = json.dumps(
            {
                "query": query,
                "evidence": evidence,
                "model_version": self.model_version,
                "artifact_sha256": self.artifact_sha256,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            with urlopen(Request(self.url, data=payload, headers=headers, method="POST"), timeout=self.timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            return self._fallback(f"request_failed:{type(exc).__name__}")

        answer = result.get("answer")
        served_version = result.get("model_version")
        served_sha = result.get("artifact_sha256")
        if not isinstance(answer, str) or not answer.strip():
            return self._fallback("empty_answer")
        if served_version != self.model_version:
            return self._fallback("model_version_mismatch")
        if self.artifact_sha256 and served_sha != self.artifact_sha256:
            return self._fallback("artifact_checksum_mismatch")
        allowed = {str(item["evidence_id"]) for item in evidence}
        citations = extract_citations(answer)
        if not citations or not set(citations).issubset(allowed):
            return self._fallback("citation_contract_violation")
        return AnswerModelOutcome(
            answer=answer.strip(),
            mode="answer_model",
            model_version=served_version,
            artifact_sha256=served_sha,
        )

    def _fallback(self, reason: str) -> AnswerModelOutcome:
        return AnswerModelOutcome(
            answer=None,
            mode="deterministic_fallback",
            model_version=self.model_version,
            artifact_sha256=self.artifact_sha256,
            fallback_reason=reason,
        )
