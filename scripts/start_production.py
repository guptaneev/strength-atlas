"""Validate the optional model artifact, then start the production API."""

from __future__ import annotations

import logging
import os

from model_artifact import ensure_model_from_env


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        ensure_model_from_env()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("atlas.startup").error(
            "reranker activation failed; starting baseline retrieval error_type=%s",
            exc.__class__.__name__,
        )
        os.environ.pop("ATLAS_RERANKER_MODEL_PATH", None)

    port = os.getenv("PORT", "8000")
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "atlas.api.app:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
            "--proxy-headers",
            "--forwarded-allow-ips=*",
        ],
    )


if __name__ == "__main__":
    main()
