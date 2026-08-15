"""Package, download, validate, and cache the optional reranker artifact."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
from urllib.request import Request, urlopen
from urllib.parse import quote, urlsplit, urlunsplit

LOGGER = logging.getLogger("atlas.model_artifact")
REQUIRED_FILES = ("config.json", "model.safetensors", "tokenizer_config.json")
DEFAULT_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
GCP_METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/"
    "service-accounts/default/token"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_model(path: Path, expected_weights_sha256: str) -> None:
    if not path.is_dir():
        raise FileNotFoundError("model directory is missing")
    for name in REQUIRED_FILES:
        if not (path / name).is_file():
            raise ValueError(f"model artifact is missing required file: {name}")
    actual = sha256_file(path / "model.safetensors")
    if actual != expected_weights_sha256.lower():
        raise ValueError("model weights checksum mismatch")


def ensure_model_from_env() -> bool:
    model_path_raw = os.getenv("ATLAS_RERANKER_MODEL_PATH", "").strip()
    if not model_path_raw:
        LOGGER.info("reranker disabled; starting with baseline retrieval")
        return False

    model_path = Path(model_path_raw)
    weights_sha256 = os.getenv("ATLAS_RERANKER_WEIGHTS_SHA256", "").strip().lower()
    model_url = os.getenv("ATLAS_RERANKER_MODEL_URL", "").strip()
    archive_sha256 = os.getenv("ATLAS_RERANKER_ARCHIVE_SHA256", "").strip().lower()
    model_version = os.getenv("ATLAS_RERANKER_MODEL_VERSION", model_path.name).strip()

    if not weights_sha256:
        raise ValueError("ATLAS_RERANKER_WEIGHTS_SHA256 is required when reranking is enabled")

    try:
        validate_model(model_path, weights_sha256)
        LOGGER.info("reranker cache hit version=%s", model_version)
        return True
    except (FileNotFoundError, ValueError):
        if not model_url:
            raise

    if not archive_sha256:
        raise ValueError("ATLAS_RERANKER_ARCHIVE_SHA256 is required for model downloads")

    model_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="atlas-model-", dir=model_path.parent) as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)
        archive_path = temp_dir / "model.tar.gz"
        _download(model_url, archive_path)
        if sha256_file(archive_path) != archive_sha256:
            raise ValueError("model archive checksum mismatch")

        extract_root = temp_dir / "extracted"
        extract_root.mkdir()
        _safe_extract(archive_path, extract_root)
        artifact_root = _find_artifact_root(extract_root)
        validate_model(artifact_root, weights_sha256)

        staged = model_path.parent / f".{model_path.name}.staged"
        if staged.exists():
            shutil.rmtree(staged)
        shutil.copytree(artifact_root, staged)
        if model_path.exists():
            backup = model_path.parent / f".{model_path.name}.previous"
            if backup.exists():
                shutil.rmtree(backup)
            model_path.replace(backup)
        staged.replace(model_path)

    _write_manifest(model_path, model_version, archive_sha256, weights_sha256, model_url)
    LOGGER.info("reranker downloaded and verified version=%s", model_version)
    return True


def package_model(source: Path, output: Path, version: str) -> dict[str, str]:
    weights_sha256 = sha256_file(source / "model.safetensors")
    validate_model(source, weights_sha256)
    output.parent.mkdir(parents=True, exist_ok=True)
    paths = [source, *sorted(source.rglob("*"))]
    with output.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for path in paths:
                if path.is_symlink():
                    raise ValueError("model source may not contain links")
                relative = Path(version) / path.relative_to(source)
                info = archive.gettarinfo(str(path), arcname=str(relative))
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = 0
                info.mode = 0o755 if path.is_dir() else 0o644
                if path.is_file():
                    with path.open("rb") as handle:
                        archive.addfile(info, handle)
                else:
                    archive.addfile(info)
    return {
        "model_version": version,
        "archive_sha256": sha256_file(output),
        "weights_sha256": weights_sha256,
        "archive": str(output),
    }


def _download(url: str, output: Path) -> None:
    max_bytes = int(os.getenv("ATLAS_RERANKER_MAX_ARCHIVE_BYTES", str(DEFAULT_MAX_ARCHIVE_BYTES)))
    headers = {"User-Agent": "strength-atlas-model-fetch/1"}
    parsed = urlsplit(url)
    request_url = url
    if parsed.scheme == "gs":
        request_url = _gcs_download_url(parsed)
        headers["Authorization"] = f"Bearer {_gcp_access_token()}"
    else:
        auth_token = os.getenv("ATLAS_RERANKER_MODEL_AUTH_TOKEN", "").strip()
        api_key = os.getenv("ATLAS_RERANKER_MODEL_API_KEY", "").strip()
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        if api_key:
            headers["apikey"] = api_key
    request = Request(request_url, headers=headers)
    total = 0
    with urlopen(request, timeout=60) as response, output.open("wb") as handle:  # noqa: S310
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("model archive exceeds configured size limit")
            handle.write(chunk)


def _gcs_download_url(parsed) -> str:
    bucket = parsed.netloc
    object_name = parsed.path.lstrip("/")
    if not bucket or not object_name or parsed.query or parsed.fragment:
        raise ValueError("GCS model URL must be gs://BUCKET/OBJECT")
    return (
        "https://storage.googleapis.com/storage/v1/b/"
        f"{quote(bucket, safe='')}/o/{quote(object_name, safe='')}?alt=media"
    )


def _gcp_access_token() -> str:
    request = Request(GCP_METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"})
    with urlopen(request, timeout=10) as response:  # noqa: S310
        payload = json.load(response)
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise ValueError("Cloud Run metadata server did not return an access token")
    return token


def _safe_extract(archive_path: Path, destination: Path) -> None:
    destination_resolved = destination.resolve()
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            if member.issym() or member.islnk():
                raise ValueError("model archive may not contain links")
            member_path = (destination / member.name).resolve()
            if destination_resolved not in member_path.parents and member_path != destination_resolved:
                raise ValueError("model archive contains an unsafe path")
        archive.extractall(destination, filter="data")


def _find_artifact_root(root: Path) -> Path:
    if all((root / name).is_file() for name in REQUIRED_FILES):
        return root
    matches = [path.parent for path in root.rglob("model.safetensors")]
    valid = [path for path in matches if all((path / name).is_file() for name in REQUIRED_FILES)]
    if len(valid) != 1:
        raise ValueError("model archive must contain exactly one model artifact")
    return valid[0]


def _write_manifest(path: Path, version: str, archive_sha256: str, weights_sha256: str, url: str) -> None:
    parsed = urlsplit(url)
    safe_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    manifest = {
        "model_version": version,
        "archive_sha256": archive_sha256,
        "weights_sha256": weights_sha256,
        "source_url": safe_url,
    }
    (path / "artifact-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("ensure", help="ensure the environment-configured model is cached and valid")
    package = subparsers.add_parser("package", help="create a versioned model archive")
    package.add_argument("--source", type=Path, required=True)
    package.add_argument("--output", type=Path, required=True)
    package.add_argument("--version", required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if args.command == "ensure":
        ensure_model_from_env()
        return 0
    print(json.dumps(package_model(args.source, args.output, args.version), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
