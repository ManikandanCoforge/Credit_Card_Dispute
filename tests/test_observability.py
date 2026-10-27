"""Tracing setup for bank API calls and narrative model calls."""

import json

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import ProxyTracerProvider, StatusCode

from src import observability
from src.observability import (
    configure_tracing,
    set_http_status,
    set_model_usage,
    shutdown_tracing,
    trace_api_call,
    trace_model_call,
)

# Taken at import, before any test installs a provider.
_PROVIDER_AT_IMPORT = observability._provider
_GLOBAL_AT_IMPORT = trace.get_tracer_provider()


def test_importing_the_module_does_not_install_a_provider():
    assert _PROVIDER_AT_IMPORT is None
    assert isinstance(_GLOBAL_AT_IMPORT, ProxyTracerProvider)


def test_configure_tracing_installs_one_provider_and_shuts_it_down(monkeypatch):
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    exporter = InMemorySpanExporter()
    provider = configure_tracing(exporter)

    assert trace.get_tracer_provider() is provider
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
    assert "stderr-probe" not in captured.out


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


def _tracer():
    exporter = InMemorySpanExporter()
    provider = TracerProvider(shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test"), exporter
