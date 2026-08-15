from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

from scripts import model_artifact
from scripts.model_artifact import ensure_model_from_env, package_model, validate_model


def _artifact(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "config.json").write_text("{}", encoding="utf-8")
    (root / "tokenizer_config.json").write_text("{}", encoding="utf-8")
    (root / "model.safetensors").write_bytes(b"test-weights")
    return root


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def test_package_download_validate_and_cache_model(tmp_path, monkeypatch) -> None:
    source = _artifact(tmp_path / "source")
    archive = tmp_path / "release" / "model.tar.gz"
    manifest = package_model(source, archive, "model-v1")
    second_archive = tmp_path / "release" / "model-second.tar.gz"
    second_manifest = package_model(source, second_archive, "model-v1")
    assert second_manifest["archive_sha256"] == manifest["archive_sha256"]
    target = tmp_path / "cache" / "model-v1"
    monkeypatch.setenv("ATLAS_RERANKER_MODEL_PATH", str(target))
    monkeypatch.setenv("ATLAS_RERANKER_MODEL_URL", archive.as_uri())
    monkeypatch.setenv("ATLAS_RERANKER_ARCHIVE_SHA256", manifest["archive_sha256"])
    monkeypatch.setenv("ATLAS_RERANKER_WEIGHTS_SHA256", manifest["weights_sha256"])
    monkeypatch.setenv("ATLAS_RERANKER_MODEL_VERSION", "model-v1")

    assert ensure_model_from_env() is True
    assert (target / "artifact-manifest.json").is_file()
    assert ensure_model_from_env() is True


def test_validate_model_rejects_malformed_artifact(tmp_path) -> None:
    malformed = tmp_path / "malformed"
    malformed.mkdir()
    with pytest.raises(ValueError, match="required file"):
        validate_model(malformed, _sha256(b"test-weights"))


def test_download_rejects_archive_checksum_mismatch(tmp_path, monkeypatch) -> None:
    source = _artifact(tmp_path / "source")
    archive = tmp_path / "model.tar.gz"
    manifest = package_model(source, archive, "model-v1")
    monkeypatch.setenv("ATLAS_RERANKER_MODEL_PATH", str(tmp_path / "cache" / "model-v1"))
    monkeypatch.setenv("ATLAS_RERANKER_MODEL_URL", archive.as_uri())
    monkeypatch.setenv("ATLAS_RERANKER_ARCHIVE_SHA256", "0" * 64)
    monkeypatch.setenv("ATLAS_RERANKER_WEIGHTS_SHA256", manifest["weights_sha256"])
    with pytest.raises(ValueError, match="archive checksum"):
        ensure_model_from_env()


def test_gcs_download_uses_cloud_run_identity_without_static_credentials(tmp_path, monkeypatch) -> None:
    calls = []

    class _Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def _urlopen(request, timeout):
        calls.append((request, timeout))
        if request.full_url == model_artifact.GCP_METADATA_TOKEN_URL:
            assert request.get_header("Metadata-flavor") == "Google"
            return _Response(json.dumps({"access_token": "test-token"}).encode())
        assert request.full_url == (
            "https://storage.googleapis.com/storage/v1/b/atlas-models/o/"
            "models%2Fmodel%20v1.tar.gz?alt=media"
        )
        assert request.get_header("Authorization") == "Bearer test-token"
        return _Response(b"archive")

    monkeypatch.setattr(model_artifact, "urlopen", _urlopen)
    output = tmp_path / "model.tar.gz"
    model_artifact._download("gs://atlas-models/models/model v1.tar.gz", output)

    assert output.read_bytes() == b"archive"
    assert len(calls) == 2
