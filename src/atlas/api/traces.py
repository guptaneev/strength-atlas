from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def append_retrieval_trace(path: str, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, default=str, sort_keys=True))
        fh.write("\n")
