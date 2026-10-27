"""Tracing for bank API calls and narrative model calls.

Importing this module does not install a provider and does not emit a span.
``configure_tracing()`` does that. The complaint flow does not call it yet.

Finished spans go to a ``SpanStore``. ``start_tracing()`` uses SQLite. Pass
another store to keep the same spans somewhere else.

A span records the method, path, model name, operation, response status, and
token counts. It does not record a query string, body, header, prompt, or
completion. A method, model, or operation that is not a short identifier, or
a path that is not a short path, is stored as ``redacted``.
"""

import json
import os
import re
import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF
from opentelemetry.trace import Span, Status, StatusCode, Tracer

from src.span_store.base import SpanRecord, SpanStore
from src.span_store.sqlite import SqliteSpanStore

_SERVICE_NAME = "fde-card-disputes-training"
_REDACTED = "redacted"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
_MAX_PATH_LENGTH = 256

_provider: TracerProvider | None = None
_closed = False


def configure_tracing(exporter: SpanExporter | None = None) -> TracerProvider:
    """Install one process-wide provider.

    A second call returns the provider already installed. Set
    ``OTEL_SDK_DISABLED=true`` to install a provider that records nothing.
    With no exporter, spans are printed to stderr.
    """
    global _provider
    if _provider is not None:
        return _provider
    provider = _build_provider(exporter)
    trace.set_tracer_provider(provider)
    _provider = provider
    return provider


def shutdown_tracing() -> None:
    """Flush the installed provider and shut it down.

    A second call, or a call before ``configure_tracing()``, does nothing.
    """
    global _closed
    if _provider is None or _closed:
        return
    _provider.force_flush()
    _provider.shutdown()
    _closed = True


@contextmanager
def trace_api_call(
    method: str, path: str, *, tracer: Tracer | None = None
) -> Iterator[Span]:
    """Span for one bank HTTP call.

    The span is named ``HTTP {method}``. Set the response status with
    ``set_http_status``. An exception marks the span ``ERROR`` and records
    the exception class, not the message.
    """
    safe_method = _identifier(method)
    with _recording(
        f"HTTP {safe_method}",
        {"http.request.method": safe_method, "url.path": _path(path)},
        tracer=tracer,
    ) as span:
        yield span


@contextmanager
def trace_model_call(
    model: str, operation: str, *, tracer: Tracer | None = None
) -> Iterator[Span]:
    """Span for one narrative model call.

    The span is named ``{operation} {model}``. Set token counts with
    ``set_model_usage``. An exception marks the span ``ERROR`` and records
    the exception class, not the message.
    """
    safe_model = _identifier(model)
    safe_operation = _identifier(operation)
    with _recording(
        f"{safe_operation} {safe_model}",
        {
            "gen_ai.operation.name": safe_operation,
            "gen_ai.request.model": safe_model,
        },
        tracer=tracer,
    ) as span:
        yield span


def set_http_status(span: Span, status_code: int) -> None:
    """Record the HTTP status on a span from ``trace_api_call``."""
    span.set_attribute("http.response.status_code", status_code)


def set_model_usage(span: Span, input_tokens: int, output_tokens: int) -> None:
    """Record token counts on a span from ``trace_model_call``."""
    span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
    span.set_attribute("gen_ai.usage.output_tokens", output_tokens)


@contextmanager
def trace_case(case_id: str, *, tracer: Tracer | None = None) -> Iterator[Span]:
    """Span for one complaint. Bank calls made inside it are its children."""
    safe_case = _identifier(case_id)
    with _recording(f"case {safe_case}", {"case_id": safe_case}, tracer=tracer) as span:
        yield span


def set_case_result(
    span: Span,
    *,
    classification: str,
    routing: str,
    missing_information: list[str],
    check: str,
) -> None:
    """Record the decision on a span from ``trace_case``."""
    span.set_attribute("classification", _identifier(classification))
    span.set_attribute("routing", _identifier(routing))
    span.set_attribute("missing_information", _identifiers(missing_information))
    span.set_attribute("check", _identifier(check))


def set_case_check(span: Span, check: str) -> None:
    """Record which check stopped the case, without the exception message."""
    span.set_attribute("check", _identifier(check))


def _build_provider(exporter: SpanExporter | None) -> TracerProvider:
    resource = Resource.create({"service.name": _SERVICE_NAME})
    if _sdk_disabled():
        return TracerProvider(resource=resource, sampler=ALWAYS_OFF)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(_sink(exporter)))
    return provider


def _sink(exporter: SpanExporter | None) -> SpanExporter:
    # stderr keeps a later startup trace from mixing with the JSON on stdout.
    if exporter is None:
        return ConsoleSpanExporter(out=sys.stderr, formatter=_console_span)
    return exporter


def _console_span(span: ReadableSpan) -> str:
    body = json.loads(span.to_json())
    for key in ("resource", "events", "links"):
        body.pop(key, None)
    context = body.get("context")
    if isinstance(context, dict):
        context.pop("trace_state", None)
    printed: dict[str, object] = {}
    for key, value in body.items():
        printed[key] = value
        if key == "end_time":
            printed["latency_ms"] = _latency_ms(span)
    return json.dumps(printed, indent=4) + "\n"


def _latency_ms(span: ReadableSpan) -> float | None:
    start = span.start_time
    end = span.end_time
    if start is None or end is None:
        return None
    return (end - start) / 1_000_000


def _sdk_disabled() -> bool:
    return os.environ.get("OTEL_SDK_DISABLED", "").strip().lower() == "true"


class SpanStoreExporter(SpanExporter):
    """Present a ``SpanStore`` to the tracing SDK."""

    def __init__(self, store: SpanStore) -> None:
        self._store = store
        self._closed = False

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if self._closed:
            return SpanExportResult.FAILURE
        for span in spans:
            self._store.write(_span_record(span))
        self._store.flush()
        return SpanExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        del timeout_millis
        if not self._closed:
            self._store.flush()
        return True

    def shutdown(self) -> None:
        if self._closed:
            return
        self._store.close()
        self._closed = True


def start_tracing(
    path: str | Path | None = None, *, store: SpanStore | None = None
) -> TracerProvider:
    """Keep finished spans in ``store``.

    With no store, spans go to SQLite. ``path`` or ``TRACE_DB`` chooses that
    file, and ``path`` is ignored when ``store`` is given. A second call keeps
    the store already open. Nothing in the complaint flow calls this yet.
    """
    if _provider is not None:
        return _provider
    if store is None:
        if path is None:
            path = os.environ.get("TRACE_DB", os.path.join(".state", "traces.sqlite3"))
        store = SqliteSpanStore(path)
    return configure_tracing(SpanStoreExporter(store))


def _span_record(span: ReadableSpan) -> SpanRecord:
    row = json.loads(_console_span(span))
    context = row["context"]
    return {
        "trace_id": context["trace_id"],
        "span_id": context["span_id"],
        "parent_id": row["parent_id"],
        "name": row["name"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "latency_ms": row["latency_ms"],
        "status": row["status"]["status_code"],
        "attributes": row["attributes"],
    }


@contextmanager
def _recording(
    name: str, attributes: Mapping[str, str], *, tracer: Tracer | None
) -> Iterator[Span]:
    active = tracer if tracer is not None else _package_tracer()
    # The SDK otherwise records the exception message and puts it on the status.
    with active.start_as_current_span(
        name, record_exception=False, set_status_on_exception=False
    ) as span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR))
            span.set_attribute("error.type", type(exc).__name__)
            raise


def _package_tracer() -> Tracer:
    if _provider is not None:
        return _provider.get_tracer(_SERVICE_NAME)
    return trace.get_tracer(_SERVICE_NAME)


def _identifiers(values: list[str]) -> str:
    safe = [_identifier(value) for value in values]
    if _REDACTED in safe:
        return _REDACTED
    return ",".join(safe)


def _identifier(value: str) -> str:
    if _IDENTIFIER.fullmatch(value):
        return value
    return _REDACTED


def _path(value: str) -> str:
    if (
        value.startswith("/")
        and "?" not in value
        and "#" not in value
        and len(value) <= _MAX_PATH_LENGTH
    ):
        return value
    return _REDACTED
