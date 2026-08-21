from fastapi.testclient import TestClient

from atlas.ml.answer_server import AnswerServerConfig, create_answer_model_app


class StubRuntime:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    def generate(self, *, query: str, evidence: list[dict[str, str]]) -> str:
        return self.answer


def config() -> AnswerServerConfig:
    return AnswerServerConfig(
        model_id="base",
        adapter_path="adapter",
        model_version="dpo-v1",
        artifact_sha256="a" * 64,
        api_key="secret",
    )


def payload() -> dict:
    return {
        "query": "What program?",
        "evidence": [{"evidence_id": "e1", "text": "Use the example program."}],
        "model_version": "dpo-v1",
        "artifact_sha256": "a" * 64,
    }


def test_answer_server_enforces_auth_version_and_citations() -> None:
    client = TestClient(create_answer_model_app(config=config(), runtime=StubRuntime("Use it [e1].")))

    assert client.post("/v1/generate", json=payload()).status_code == 401
    response = client.post(
        "/v1/generate", json=payload(), headers={"Authorization": "Bearer secret"}
    )
    assert response.status_code == 200
    assert response.json()["model_version"] == "dpo-v1"

    mismatch = payload()
    mismatch["model_version"] = "wrong"
    assert client.post(
        "/v1/generate", json=mismatch, headers={"Authorization": "Bearer secret"}
    ).status_code == 409


def test_answer_server_rejects_unknown_or_missing_citations() -> None:
    headers = {"Authorization": "Bearer secret"}
    unknown = TestClient(
        create_answer_model_app(config=config(), runtime=StubRuntime("Unsupported [e9]."))
    )
    missing = TestClient(
        create_answer_model_app(config=config(), runtime=StubRuntime("Unsupported."))
    )

    assert unknown.post("/v1/generate", json=payload(), headers=headers).status_code == 502
    assert missing.post("/v1/generate", json=payload(), headers=headers).status_code == 502
