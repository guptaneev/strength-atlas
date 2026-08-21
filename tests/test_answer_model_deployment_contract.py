from pathlib import Path


def test_answer_model_deployment_keeps_gpu_service_private_and_pinned() -> None:
    script = Path("scripts/deploy_answer_model_cloud_run.sh").read_text(encoding="utf-8")

    assert "--gpu 1" in script
    assert "--gpu-type nvidia-l4" in script
    assert "--no-allow-unauthenticated" in script
    assert "ATLAS_ANSWER_SERVER_ARTIFACT_SHA256" in script
    assert "ATLAS_ANSWER_SERVER_MODEL_VERSION" in script
    assert "atlas-answer-model-api-key" in script
