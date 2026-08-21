"""GPU answer-model service with version, checksum, auth, and citation gates."""

from __future__ import annotations

from dataclasses import dataclass
import os
from threading import Lock
from typing import Any, Protocol

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from atlas.ml.answer_evaluation import extract_citations


SYSTEM_PROMPT = (
    "Answer only from the supplied evidence. Every factual statement must cite "
    "an evidence ID such as [e1]. If evidence is insufficient, say so plainly."
)


class EvidenceItem(BaseModel):
    evidence_id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=12_000)


class GenerateRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)
    evidence: list[EvidenceItem] = Field(min_length=1, max_length=100)
    model_version: str = Field(min_length=1, max_length=200)
    artifact_sha256: str | None = Field(default=None, min_length=64, max_length=64)


class GenerateResponse(BaseModel):
    answer: str
    model_version: str
    artifact_sha256: str | None


class AnswerRuntime(Protocol):
    def generate(self, *, query: str, evidence: list[dict[str, str]]) -> str: ...


@dataclass(frozen=True)
class AnswerServerConfig:
    model_id: str
    adapter_path: str
    model_version: str
    artifact_sha256: str | None
    api_key: str | None
    max_new_tokens: int = 180

    @classmethod
    def from_env(cls) -> "AnswerServerConfig":
        required = {
            "model_id": os.getenv("ATLAS_ANSWER_SERVER_MODEL_ID"),
            "adapter_path": os.getenv("ATLAS_ANSWER_SERVER_ADAPTER_PATH"),
            "model_version": os.getenv("ATLAS_ANSWER_SERVER_MODEL_VERSION"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"Missing answer-server settings: {', '.join(missing)}")
        return cls(
            model_id=str(required["model_id"]),
            adapter_path=str(required["adapter_path"]),
            model_version=str(required["model_version"]),
            artifact_sha256=os.getenv("ATLAS_ANSWER_SERVER_ARTIFACT_SHA256") or None,
            api_key=os.getenv("ATLAS_ANSWER_SERVER_API_KEY") or None,
            max_new_tokens=int(os.getenv("ATLAS_ANSWER_SERVER_MAX_NEW_TOKENS", "180")),
        )


class HuggingFaceAnswerRuntime:
    def __init__(self, config: AnswerServerConfig) -> None:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if not torch.cuda.is_available():
            raise RuntimeError("A CUDA GPU is required for the 3B answer-model service")
        self.config = config
        self.tokenizer = AutoTokenizer.from_pretrained(config.model_id)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        base = AutoModelForCausalLM.from_pretrained(
            config.model_id,
            torch_dtype=torch.float16,
            device_map={"": torch.cuda.current_device()},
        )
        self.model = PeftModel.from_pretrained(base, config.adapter_path)
        self.model.eval()

    def generate(self, *, query: str, evidence: list[dict[str, str]]) -> str:
        import torch

        evidence_text = "\n".join(f"[{row['evidence_id']}] {row['text']}" for row in evidence)
        prompt = self.tokenizer.apply_chat_template(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Evidence:\n{evidence_text}\n\nQuestion: {query}"},
            ],
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        with torch.inference_mode():
            output = self.model.generate(
                **inputs,
                max_new_tokens=self.config.max_new_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        return self.tokenizer.decode(
            output[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
        ).strip()


class LazyAnswerRuntime:
    def __init__(self, config: AnswerServerConfig) -> None:
        self.config = config
        self._runtime: AnswerRuntime | None = None
        self._lock = Lock()

    def generate(self, *, query: str, evidence: list[dict[str, str]]) -> str:
        if self._runtime is None:
            with self._lock:
                if self._runtime is None:
                    self._runtime = HuggingFaceAnswerRuntime(self.config)
        return self._runtime.generate(query=query, evidence=evidence)


def create_answer_model_app(
    *,
    config: AnswerServerConfig | None = None,
    runtime: AnswerRuntime | None = None,
) -> FastAPI:
    resolved = config or AnswerServerConfig.from_env()
    generator = runtime or LazyAnswerRuntime(resolved)
    app = FastAPI(title="Strength Atlas Answer Model", version=resolved.model_version)

    def authorize(authorization: str | None = Header(default=None)) -> None:
        if not resolved.api_key:
            return
        if authorization != f"Bearer {resolved.api_key}":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    @app.get("/healthz")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "model_version": resolved.model_version,
            "artifact_sha256": resolved.artifact_sha256,
        }

    @app.post("/v1/generate", response_model=GenerateResponse, dependencies=[Depends(authorize)])
    def generate(request: GenerateRequest) -> GenerateResponse:
        if request.model_version != resolved.model_version:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Model version mismatch")
        if resolved.artifact_sha256 and request.artifact_sha256 != resolved.artifact_sha256:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Artifact checksum mismatch")
        evidence = [row.model_dump() for row in request.evidence]
        answer = generator.generate(query=request.query, evidence=evidence).strip()
        allowed = {row.evidence_id for row in request.evidence}
        citations = extract_citations(answer)
        if not answer or not citations or not set(citations).issubset(allowed):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Citation contract violation")
        return GenerateResponse(
            answer=answer,
            model_version=resolved.model_version,
            artifact_sha256=resolved.artifact_sha256,
        )

    return app


def _default_app() -> FastAPI:
    try:
        return create_answer_model_app()
    except RuntimeError as exc:
        detail = str(exc)
        app = FastAPI(title="Strength Atlas Answer Model")

        @app.get("/healthz", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
        def unhealthy() -> dict[str, str]:
            return {"status": "configuration_error", "detail": detail}

        return app


app = _default_app()
