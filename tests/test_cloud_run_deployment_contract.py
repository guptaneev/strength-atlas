from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cloud_run_deploy_keeps_cost_and_state_bounded() -> None:
    script = (ROOT / "scripts" / "deploy_cloud_run.sh").read_text(encoding="utf-8")
    assert '--memory 1Gi' in script
    assert '--min 0' in script
    assert '--max 1' in script
    assert '--concurrency 1' in script
    assert '--cpu-throttling' in script
    assert '--no-cpu-boost' in script
    assert script.index('gcloud run jobs execute') < script.index('gcloud run deploy "$service_name"')


def test_cloud_run_config_contains_no_secret_values() -> None:
    config = (ROOT / "configs" / "cloud-run.env.example.yaml").read_text(encoding="utf-8")
    assert "ATLAS_DATABASE_URL" not in config
    assert "ATLAS_SUPABASE_SERVICE_KEY" not in config
    assert "ATLAS_BROWSER_USE_API_KEY" not in config
    assert "ATLAS_RERANKER_MODEL_AUTH_TOKEN" not in config
    assert "ATLAS_RERANKER_MODEL_API_KEY" not in config
    assert "bootstrap.invalid" in config


def test_cloud_run_uses_runtime_identity_for_private_model_storage() -> None:
    script = (ROOT / "scripts" / "deploy_cloud_run.sh").read_text(encoding="utf-8")
    assert "storage.googleapis.com" in script
    assert "ATLAS_RERANKER_MODEL_AUTH_TOKEN" not in script
    assert "ATLAS_RERANKER_MODEL_API_KEY" not in script
    assert "gs://REPLACE_PROJECT_ID-models" in (
        ROOT / "configs" / "cloud-run.env.example.yaml"
    ).read_text(encoding="utf-8")
