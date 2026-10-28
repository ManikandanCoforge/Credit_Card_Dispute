"""Container entrypoint for the POC deployment.

The repository's own CLI (tools/runtime.py) binds the fictional bank API to
127.0.0.1 only and has no --host flag, so a container needs this thin wrapper to
listen on 0.0.0.0 behind a load balancer. No application code changes; this file
reuses create_server() unchanged.

Environment:
    BANK_DATA_DIR   dataset directory (default data/dev)
    BANK_STATE      SQLite state file (default /app/.state/mock.sqlite)
    BANK_HOST       bind address (default 0.0.0.0)
    BANK_PORT       bind port (default 8000, falls back to PORT)
"""
import os
import signal
import sys
from pathlib import Path

from tools.runtime import create_server


def main() -> int:
    data_dir = Path(os.environ.get("BANK_DATA_DIR", "data/dev"))
    state = Path(os.environ.get("BANK_STATE", "/app/.state/mock.sqlite"))
    host = os.environ.get("BANK_HOST", "0.0.0.0")
    port = int(os.environ.get("BANK_PORT", os.environ.get("PORT", "8000")))
    state.parent.mkdir(parents=True, exist_ok=True)
    server = create_server(data_dir, state, host=host, port=port)
    print(f"serving data={data_dir} state={state} on http://{host}:{port}", flush=True)

    def stop(*_):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
