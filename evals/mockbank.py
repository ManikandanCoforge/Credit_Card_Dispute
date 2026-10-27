"""Start the supplied mock on a private port and read back its audit trail.

The suite never reads `dataset.json` as a substitute for a tool call. It reads
the audit the mock wrote, which is the only record of what the application
actually asked for.
"""

from __future__ import annotations

import json
import socket
import sqlite3

# Runs this repository's own mock server.
import subprocess  # nosec B404
import sys
import time
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from evals.dataset import REPO_ROOT, SuiteError

STARTUP_TIMEOUT_S = 10.0
"""How long the mock gets to answer /health before the run fails."""


def free_port() -> int:
    """Return a port the OS has just confirmed is free."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def running_mock(data_dir: Path, state_path: Path) -> Iterator[str]:
    """Run `tools/runtime.py serve` for one dataset and yield its base URL."""
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    # Fixed argv, never a shell.
    process = subprocess.Popen(  # nosec B603
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "runtime.py"),
            "serve",
            "--data",
            str(data_dir),
            "--state",
            str(state_path),
            "--port",
            str(port),
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_until_healthy(base_url, process)
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        if process.stderr is not None:
            process.stderr.close()


def _wait_until_healthy(base_url: str, process: subprocess.Popen[str]) -> None:
    """Poll /health until the mock answers, or explain why it never did."""
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    while time.monotonic() < deadline:
        if process.poll() is not None:
            detail = (process.stderr.read() if process.stderr else "").strip()
            raise SuiteError(f"the mock exited before it was healthy: {detail}")
        try:
            # The URL is built from 127.0.0.1 and a free local port.
            with urlopen(  # nosec B310
                f"{base_url}/health", timeout=0.5
            ) as response:
                if response.status == 200:
                    return
        except (URLError, OSError):
            time.sleep(0.05)
    raise SuiteError(f"the mock did not become healthy at {base_url}")


def read_audit(state_path: Path) -> list[dict[str, object]]:
    """Return every audit row, in sequence order, from the mock's state database."""
    if not Path(state_path).exists():
        return []
    with closing(sqlite3.connect(state_path)) as database:
        database.row_factory = sqlite3.Row
        rows = database.execute("SELECT * FROM audit ORDER BY seq").fetchall()
    audit: list[dict[str, object]] = []
    for row in rows:
        record = dict(row)
        detail = record.get("detail")
        if isinstance(detail, str):
            try:
                record["detail"] = json.loads(detail)
            except json.JSONDecodeError:
                record["detail"] = {"raw": detail}
        audit.append(record)
    return audit
