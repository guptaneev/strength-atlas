from __future__ import annotations

import sys
from pathlib import Path

# Vercel loads this module from repo root. Ensure src/ is importable.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atlas.api.app import app

