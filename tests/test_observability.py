"""Tracing setup for bank API calls and narrative model calls."""

import json
import sqlite3

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import ProxyTracerProvider, StatusCode

from src import observability
from src.observability import (
    SpanStoreExporter,
    configure_tracing,
    set_case_check,
    set_case_result,
    set_http_status,
    set_model_usage,
    shutdown_tracing,
    start_tracing,
    trace_api_call,
    trace_case,
    trace_model_call,
)
from src.span_store.base import MemorySpanStore
from src.span_store.sqlite import SqliteSpanStore

# Taken at import, before any test installs a provider.
_PROVIDER_AT_IMPORT = observability._provider
_GLOBAL_AT_IMPORT = trace.get_tracer_provider()


def test_importing_the_module_does_not_install_a_provider():
    assert _PROVIDER_AT_IMPORT is None
    assert isinstance(_GLOBAL_AT_IMPORT, ProxyTracerProvider)


def test_configure_tracing_installs_one_provider_and_shuts_it_down(monkeypatch):
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    monkeypatch.setattr(observability, "_provider", None)
    monkeypatch.setattr(observability, "_closed", False)
    installed: list[object] = []
    monkeypatch.setattr(
        observability.trace,
        "set_tracer_provider",
        lambda provider: installed.append(provider),
    )
    exporter = InMemorySpanExporter()
    provider = configure_tracing(exporter)

    assert installed == [provider]
    assert provider.resource.attributes["service.name"] == "fde-card-disputes-training"
    assert configure_tracing(InMemorySpanExporter()) is provider

    with provider.get_tracer("fde-card-disputes-training").start_as_current_span("installed"):
        pass
    assert [span.name for span in exporter.get_finished_spans()] == ["installed"]

    calls: list[str] = []
    force_flush = provider.force_flush
    shutdown = provider.shutdown

    def flushing(timeout_millis: int = 30000) -> bool:
        calls.append("flush")
        return force_flush(timeout_millis)

    def shutting() -> None:
        calls.append("shutdown")
        shutdown()

    provider.force_flush = flushing
    provider.shutdown = shutting
    shutdown_tracing()
    assert calls == ["flush", "shutdown"]
    shutdown_tracing()
    assert calls == ["flush", "shutdown"]


def test_a_disabled_sdk_records_nothing(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.setattr(observability, "_provider", None)
    monkeypatch.setattr(observability.trace, "set_tracer_provider", lambda _provider: None)
    exporter = InMemorySpanExporter()
    provider = configure_tracing(exporter)

    with provider.get_tracer("fde-card-disputes-training").start_as_current_span("hidden") as span:
        assert span.is_recording() is False
    assert exporter.get_finished_spans() == ()


def test_the_default_exporter_writes_to_stderr(monkeypatch, capsys):
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    monkeypatch.setattr(observability, "_provider", None)
    monkeypatch.setattr(observability.trace, "set_tracer_provider", lambda _provider: None)
    provider = configure_tracing()

    with provider.get_tracer("fde-card-disputes-training").start_as_current_span("stderr-probe"):
        pass

    captured = capsys.readouterr()
    printed = json.loads(captured.err)
    assert printed["name"] == "stderr-probe"
    assert "resource" not in printed
    assert "events" not in printed
    assert "links" not in printed
    assert "trace_state" not in printed["context"]
    keys = list(printed)
    assert keys.index("latency_ms") == keys.index("end_time") + 1
    assert printed["latency_ms"] >= 0
    assert "stderr-probe" not in captured.out


def test_an_open_span_has_no_latency_yet():
    provider = TracerProvider(shutdown_on_exit=False)
    span = provider.get_tracer("test").start_span("open")
    assert observability._latency_ms(span) is None
    span.end()


def test_shutdown_without_a_provider_does_nothing(monkeypatch):
    monkeypatch.setattr(observability, "_provider", None)
    monkeypatch.setattr(observability, "_closed", False)

    shutdown_tracing()

    assert observability._provider is None
    assert observability._closed is False


def test_an_api_span_records_the_method_path_and_status():
    tracer, exporter = _tracer()

    with trace_api_call("GET", "/v1/cases/CARD-D01/transactions", tracer=tracer) as span:
        set_http_status(span, 200)

    finished = exporter.get_finished_spans()[0]
    assert finished.name == "HTTP GET"
    assert dict(finished.attributes) == {
        "http.request.method": "GET",
        "url.path": "/v1/cases/CARD-D01/transactions",
        "http.response.status_code": 200,
    }


def test_a_model_span_records_the_model_operation_and_tokens():
    tracer, exporter = _tracer()

    with trace_model_call("demo.model-v1:mini", "chat", tracer=tracer) as span:
        set_model_usage(span, 11, 7)

    finished = exporter.get_finished_spans()[0]
    assert finished.name == "chat demo.model-v1:mini"
    assert dict(finished.attributes) == {
        "gen_ai.operation.name": "chat",
        "gen_ai.request.model": "demo.model-v1:mini",
        "gen_ai.usage.input_tokens": 11,
        "gen_ai.usage.output_tokens": 7,
    }


@pytest.mark.parametrize(
    ("method", "path", "stored_method", "stored_path"),
    [
        ("GET", "/v1/cases", "GET", "/v1/cases"),
        ("POST", "/" + "a" * 255, "POST", "/" + "a" * 255),
        ("A" * 64, "/v1/reviews", "A" * 64, "/v1/reviews"),
        ("NOT A METHOD", "/v1/cases", "redacted", "/v1/cases"),
        ("A" * 65, "/v1/cases", "redacted", "/v1/cases"),
        ("GET", "/v1/cases?token=1", "GET", "redacted"),
        ("GET", "/v1/cases#frag", "GET", "redacted"),
        ("GET", "v1/cases", "GET", "redacted"),
        ("GET", "/" + "a" * 256, "GET", "redacted"),
    ],
)
def test_a_rejected_api_value_is_stored_as_redacted(method, path, stored_method, stored_path):
    tracer, exporter = _tracer()

    with trace_api_call(method, path, tracer=tracer):
        pass

    finished = exporter.get_finished_spans()[0]
    assert finished.name == f"HTTP {stored_method}"
    assert finished.attributes["http.request.method"] == stored_method
    assert finished.attributes["url.path"] == stored_path
    if stored_method == "redacted":
        assert method not in finished.to_json()
    if stored_path == "redacted":
        assert path not in finished.to_json()


def test_a_rejected_model_name_is_stored_as_redacted():
    tracer, exporter = _tracer()

    with trace_model_call("gpt 4", "write prose", tracer=tracer):
        pass

    finished = exporter.get_finished_spans()[0]
    assert finished.name == "redacted redacted"
    assert finished.attributes["gen_ai.request.model"] == "redacted"
    assert finished.attributes["gen_ai.operation.name"] == "redacted"
    assert "gpt 4" not in finished.to_json()
    assert "write prose" not in finished.to_json()


def test_an_exception_records_its_type_and_not_its_message():
    tracer, exporter = _tracer()

    with (
        pytest.raises(RuntimeError, match="SYNTHETIC-PRIVATE-TOKEN"),
        trace_api_call("POST", "/v1/reviews", tracer=tracer),
    ):
        raise RuntimeError("SYNTHETIC-PRIVATE-TOKEN")

    finished = exporter.get_finished_spans()[0]
    assert finished.status.status_code == StatusCode.ERROR
    assert finished.attributes["error.type"] == "RuntimeError"
    assert not finished.events
    assert "SYNTHETIC-PRIVATE-TOKEN" not in finished.to_json()


def test_an_omitted_tracer_uses_the_package_tracer(monkeypatch):
    monkeypatch.setattr(observability, "_provider", None)
    tracer, exporter = _tracer()
    seen: list[str] = []

    def get_tracer(name: str, *_args: object, **_kwargs: object):
        seen.append(name)
        return tracer

    monkeypatch.setattr(observability.trace, "get_tracer", get_tracer)
    with trace_api_call("GET", "/health"):
        pass

    assert seen == ["fde-card-disputes-training"]
    assert exporter.get_finished_spans()[0].name == "HTTP GET"


def test_sqlite_stores_a_case_its_api_call_and_its_model_call(monkeypatch, tmp_path):
    _private_provider(monkeypatch)
    path = tmp_path / "traces.sqlite3"
    start_tracing(path)
    _record_card_d04()
    shutdown_tracing()

    with sqlite3.connect(path) as db:
        rows = db.execute(
            "SELECT name, span_id, parent_id, status, attributes FROM spans"
        ).fetchall()
    # Row order is not a fact this store can keep. On Windows the host clock
    # advances in roughly millisecond steps, so the case span, its API call and
    # its model call can share one start_time, and ORDER BY start_time cannot
    # recover the order they started in. Read the rows by name and pin the
    # shape instead: one root case span and two children that point at it.
    by_name = {row[0]: row for row in rows}
    assert set(by_name) == {"case CARD-D04", "HTTP GET", "chat demo.model-v1:mini"}
    case, api, model = (
        by_name["case CARD-D04"],
        by_name["HTTP GET"],
        by_name["chat demo.model-v1:mini"],
    )
    assert case[2] is None
    assert api[2] == case[1]
    assert model[2] == case[1]
    assert api[3] == "UNSET"
    assert model[3] == "UNSET"
    case_attributes = json.loads(case[4])
    assert case_attributes["missing_information"] == "authorization_confirmation"
    assert case_attributes["check"] == "ok"
    model_attributes = json.loads(model[4])
    assert model_attributes["gen_ai.request.model"] == "demo.model-v1:mini"
    assert model_attributes["gen_ai.operation.name"] == "chat"
    assert model_attributes["gen_ai.usage.input_tokens"] == 11
    assert model_attributes["gen_ai.usage.output_tokens"] == 7


def test_start_tracing_uses_trace_db_when_no_path_is_given(monkeypatch, tmp_path):
    _private_provider(monkeypatch)
    path = tmp_path / "from-env.sqlite3"
    monkeypatch.setenv("TRACE_DB", str(path))
    start_tracing()
    with trace_case("CARD-D01"):
        pass
    shutdown_tracing()

    with sqlite3.connect(path) as db:
        names = db.execute("SELECT name FROM spans").fetchall()
    assert names == [("case CARD-D01",)]


def test_a_stopped_case_records_the_check_name():
    tracer, exporter = _tracer()
    with trace_case("CARD-D04", tracer=tracer) as span:
        set_case_check(span, "failed")
    assert exporter.get_finished_spans()[0].attributes["check"] == "failed"


def test_a_rejected_missing_field_is_stored_as_redacted():
    tracer, exporter = _tracer()
    with trace_case("CARD-D04", tracer=tracer) as span:
        set_case_result(
            span,
            classification="unauthorized",
            routing="request_information",
            missing_information=["not a field"],
            check="ok",
        )
    assert exporter.get_finished_spans()[0].attributes["missing_information"] == "redacted"


def test_a_memory_store_replaces_sqlite(monkeypatch, tmp_path):
    _private_provider(monkeypatch)
    unused = tmp_path / "unused.sqlite3"
    monkeypatch.setenv("TRACE_DB", str(unused))
    store = MemorySpanStore()
    start_tracing(store=store)
    _record_card_d04()
    shutdown_tracing()

    assert not unused.exists()
    # The same coarse-clock caveat as the SQLite test above, so read by name.
    by_name = {record["name"]: record for record in store.records}
    assert set(by_name) == {"case CARD-D04", "HTTP GET", "chat demo.model-v1:mini"}
    case = by_name["case CARD-D04"]
    assert case["parent_id"] is None
    assert by_name["HTTP GET"]["parent_id"] == case["span_id"]
    model = by_name["chat demo.model-v1:mini"]
    assert model["parent_id"] == case["span_id"]
    assert model["attributes"]["gen_ai.usage.input_tokens"] == 11
    assert model["attributes"]["gen_ai.usage.output_tokens"] == 7


def test_a_second_start_tracing_keeps_the_store_already_open(monkeypatch, tmp_path):
    _private_provider(monkeypatch)
    provider = start_tracing(store=MemorySpanStore())
    unused = tmp_path / "unused.sqlite3"

    assert start_tracing(unused) is provider

    assert not unused.exists()


def test_a_second_start_tracing_does_not_open_the_trace_db(monkeypatch, tmp_path):
    _private_provider(monkeypatch)
    path = tmp_path / "from-env.sqlite3"
    monkeypatch.setenv("TRACE_DB", str(path))
    provider = start_tracing(store=MemorySpanStore())

    assert start_tracing() is provider

    assert not path.exists()


def test_a_closed_store_stops_writing(tmp_path):
    exporter = SpanStoreExporter(SqliteSpanStore(tmp_path / "traces.sqlite3"))
    assert exporter.force_flush() is True
    exporter.shutdown()
    assert exporter.export(()) is SpanExportResult.FAILURE
    assert exporter.force_flush() is True
    exporter.shutdown()


def test_a_closed_store_ignores_later_writes(tmp_path):
    sqlite = SqliteSpanStore(tmp_path / "traces.sqlite3")
    memory = MemorySpanStore()
    sqlite.close()
    memory.close()
    sqlite.write(_span_record())
    memory.write(_span_record())
    sqlite.flush()
    memory.flush()
    sqlite.close()

    assert memory.records == []
    with sqlite3.connect(tmp_path / "traces.sqlite3") as db:
        count = db.execute("SELECT COUNT(*) FROM spans").fetchone()
    assert count == (0,)


def _record_card_d04():
    with trace_case("CARD-D04") as case:
        with trace_api_call("GET", "/v1/cases/CARD-D04/transactions") as api:
            set_http_status(api, 200)
        with trace_model_call("demo.model-v1:mini", "chat") as model:
            set_model_usage(model, 11, 7)
        set_case_result(
            case,
            classification="unauthorized",
            routing="request_information",
            missing_information=["authorization_confirmation"],
            check="ok",
        )


def _span_record():
    return {
        "trace_id": "a" * 32,
        "span_id": "b" * 16,
        "parent_id": None,
        "name": "case CARD-D04",
        "start_time": None,
        "end_time": None,
        "latency_ms": None,
        "status": "UNSET",
        "attributes": {},
    }


def _private_provider(monkeypatch):
    monkeypatch.setattr(observability, "_provider", None)
    monkeypatch.setattr(observability, "_closed", False)
    monkeypatch.setattr(observability.trace, "set_tracer_provider", lambda _provider: None)


def _tracer():
    exporter = InMemorySpanExporter()
    provider = TracerProvider(shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test"), exporter
