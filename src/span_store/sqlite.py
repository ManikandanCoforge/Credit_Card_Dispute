"""Keep one row per finished span in a SQLite file."""

import json
import sqlite3
from pathlib import Path

from src.span_store.base import SpanRecord


class SqliteSpanStore:
    """SQLite adapter for ``SpanStore``."""

    def __init__(self, path: str | Path) -> None:
        location = Path(path)
        location.parent.mkdir(parents=True, exist_ok=True)
        self._db: sqlite3.Connection | None = sqlite3.connect(location)
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS spans (
                trace_id TEXT NOT NULL,
                span_id TEXT NOT NULL,
                parent_id TEXT,
                name TEXT NOT NULL,
                start_time TEXT,
                end_time TEXT,
                latency_ms REAL,
                status TEXT NOT NULL,
                attributes TEXT NOT NULL,
                PRIMARY KEY (trace_id, span_id)
            )
            """
        )
        self._db.commit()

    def write(self, record: SpanRecord) -> None:
        db = self._db
        if db is None:
            return
        db.execute(
            "INSERT INTO spans("
            "trace_id, span_id, parent_id, name, start_time, end_time, "
            "latency_ms, status, attributes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record["trace_id"],
                record["span_id"],
                record["parent_id"],
                record["name"],
                record["start_time"],
                record["end_time"],
                record["latency_ms"],
                record["status"],
                json.dumps(record["attributes"]),
            ),
        )

    def flush(self) -> None:
        db = self._db
        if db is not None:
            db.commit()

    def close(self) -> None:
        if self._db is None:
            return
        self._db.close()
        self._db = None
