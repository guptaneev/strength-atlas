from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

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
