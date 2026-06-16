from __future__ import annotations

import os
import uvicorn


def main() -> None:

    reload = os.getenv("UVICORN_RELOAD", "0").strip() == "1"

    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=reload,
        # When reload is enabled, limit watch scope to code to reduce accidental restarts
        # from uploads/logs/etc.
        reload_dirs=["src"] if reload else None,
        log_level="info",
    )


if __name__ == "__main__":

    main()


