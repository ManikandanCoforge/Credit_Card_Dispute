"""The span store interface, and a store that keeps spans in a list."""

from typing import Protocol, TypedDict


class SpanRecord(TypedDict):
    """One finished span, with the fields every store keeps."""

    trace_id: str
    span_id: str
    parent_id: str | None
    name: str
    start_time: str | None
    end_time: str | None
    latency_ms: float | None
    status: str
    attributes: dict[str, object]


class SpanStore(Protocol):
    """Where finished spans are kept.

    ``start_tracing(store=...)`` sends every finished span here. ``write``
    keeps one span, ``flush`` makes those writes durable, and ``close``
    releases the store. Later writes are ignored. A store does not talk to
    the tracing SDK.
    """

    def write(self, record: SpanRecord) -> None: ...

    def flush(self) -> None: ...

    def close(self) -> None: ...


class MemorySpanStore:
    """Keep finished spans in a list."""

    def __init__(self) -> None:
        self.records: list[SpanRecord] = []
        self._closed = False

    def write(self, record: SpanRecord) -> None:
        if self._closed:
            return
        self.records.append(record)

    def flush(self) -> None:
        return

    def close(self) -> None:
        self._closed = True
