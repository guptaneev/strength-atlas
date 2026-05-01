from __future__ import annotations

import uvicorn
import os


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("atlas.api.app:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
