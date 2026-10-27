import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from src.app import prepare_complaints
from src.load_records import (
    BankReadError,
    BankUnavailable,
    CaseListError,
    load_complaint_records,
    read_body,
)

DEV = Path(__file__).resolve().parents[1] / "data" / "dev"


def test_reachable_case_list_returns_the_card_d01_working_record():
    body = {
        "cases": [
            {
                "case_id": "CARD-D01",
                "intake_source": "CARD-D01-INTAKE",
                "documents": ["CARD-D01-INTAKE", "CARD-D01-ATTACHMENT"],
            }
        ]
    }

    with _bank(body) as base_url:
        result = load_complaint_records(base_url, DEV)

    assert result == [
        {
            "case_id": "CARD-D01",
            "intake": {
                "source_id": "CARD-D01-INTAKE",
                "statement": (
                    "I found a card purchase at Morrow Supplies for 117 crowns. "
                    "I do not recognize it and need help checking it."
                ),
                "reported_date": "2026-10-01",
                "transaction_id": "TX-D01",
                "authorization": "denied",
                "promised_service_date": "2026-08-20",
                "purchase_receipt": "attached",
                "submission_reference": "dispute-d01",
            },
            "policy": {
                "version_id": "CARD-POLICY-V2",
                "procedure_id": "CARD-PROCEDURE-01",
            },
            "missing_information": [],
            "routing": None,
        }
    ]


def test_reachable_case_list_keeps_bank_order():
    body = {
        "cases": [
            {
                "case_id": "CARD-D11",
                "intake_source": "CARD-D11-INTAKE",
                "documents": ["CARD-D11-INTAKE", "CARD-D11-ATTACHMENT"],
            },
            {
                "case_id": "CARD-D01",
                "intake_source": "CARD-D01-INTAKE",
                "documents": ["CARD-D01-INTAKE", "CARD-D01-ATTACHMENT"],
            },
        ]
    }

    with _bank(body) as base_url:
        result = load_complaint_records(base_url, DEV)

    assert result == [
        {
            "case_id": "CARD-D11",
            "intake": {
                "source_id": "CARD-D11-INTAKE",
                "statement": (
                    "I found a card purchase at Morrow Supplies for 287 crowns. "
                    "I do not recognize it and need help checking it."
                ),
                "reported_date": "2026-08-31",
                "transaction_id": "TX-D11",
                "authorization": "denied",
                "promised_service_date": "2026-08-20",
                "purchase_receipt": "attached",
                "submission_reference": "dispute-d11",
            },
            "policy": {
                "version_id": "CARD-POLICY-V1",
                "procedure_id": "CARD-PROCEDURE-01",
            },
            "missing_information": [],
            "routing": None,
        },
        {
            "case_id": "CARD-D01",
            "intake": {
                "source_id": "CARD-D01-INTAKE",
                "statement": (
                    "I found a card purchase at Morrow Supplies for 117 crowns. "
                    "I do not recognize it and need help checking it."
                ),
                "reported_date": "2026-10-01",
                "transaction_id": "TX-D01",
                "authorization": "denied",
                "promised_service_date": "2026-08-20",
                "purchase_receipt": "attached",
                "submission_reference": "dispute-d01",
            },
            "policy": {
                "version_id": "CARD-POLICY-V2",
                "procedure_id": "CARD-PROCEDURE-01",
            },
            "missing_information": [],
            "routing": None,
        },
    ]


def test_prepare_complaints_tags_a_missing_procedure_line():
    body = {
        "cases": [
            {
                "case_id": "CARD-D04",
                "intake_source": "CARD-D04-INTAKE",
                "documents": ["CARD-D04-INTAKE", "CARD-D04-ATTACHMENT"],
            },
            {
                "case_id": "CARD-D01",
                "intake_source": "CARD-D01-INTAKE",
                "documents": ["CARD-D01-INTAKE", "CARD-D01-ATTACHMENT"],
            },
        ]
    }

    with _bank(body) as base_url:
        result = prepare_complaints(base_url, DEV)

    assert result[0]["case_id"] == "CARD-D04"
    assert result[0]["missing_information"] == ["authorization_confirmation"]
    assert result[0]["routing"] == "request_information"
    assert result[1]["case_id"] == "CARD-D01"
    assert result[1]["missing_information"] == []
    assert result[1]["routing"] is None


def test_empty_case_list_returns_no_working_records():
    with _bank({"cases": []}) as base_url:
        result = load_complaint_records(base_url, DEV)

    assert result == []


def test_non_200_response_does_not_open_the_dataset(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.write_text("not a directory")
    body = {
        "cases": [
            {
                "case_id": "CARD-D01",
                "intake_source": "CARD-D01-INTAKE",
                "documents": ["CARD-D01-INTAKE"],
            }
        ]
    }

    with _bank(body, status=201) as base_url, pytest.raises(CaseListError):
        load_complaint_records(base_url, dataset)


def test_unusable_case_list_does_not_open_the_dataset(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.write_text("not a directory")
    body = {
        "cases": [
            {
                "case_id": "CARD-D01",
                "intake_source": "CARD-D01-INTAKE",
            }
        ]
    }

    with _bank(body) as base_url, pytest.raises(CaseListError):
        load_complaint_records(base_url, dataset)


def test_connection_failure_does_not_open_the_dataset(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.write_text("not a directory")

    with pytest.raises(CaseListError):
        load_complaint_records(_closed_bank(), dataset)


@pytest.mark.parametrize("base_url", ["ftp://127.0.0.1", "http://"])
def test_unusable_bank_url_does_not_open_the_dataset(tmp_path, base_url):
    dataset = tmp_path / "dataset"
    dataset.write_text("not a directory")

    with pytest.raises(CaseListError):
        load_complaint_records(base_url, dataset)


@pytest.mark.parametrize(
    ("base_url", "connection_name", "port"),
    [
        ("http://127.0.0.1", "HTTPConnection", 80),
        ("https://127.0.0.1", "HTTPSConnection", 443),
    ],
)
def test_url_without_a_port_uses_the_default_port(
    tmp_path, monkeypatch, base_url, connection_name, port
):
    seen = {}

    class Probe:
        def __init__(self, host, bound_port, timeout=None):
            seen["host"] = host
            seen["port"] = bound_port

        def request(self, method, path):
            raise OSError("closed")

        def close(self):
            return

    monkeypatch.setattr(f"src.load_records.{connection_name}", Probe)
    dataset = tmp_path / "dataset"
    dataset.write_text("not a directory")

    with pytest.raises(CaseListError):
        load_complaint_records(base_url, dataset)

    assert seen == {"host": "127.0.0.1", "port": port}


@pytest.mark.parametrize(
    ("status", "body", "retryable"),
    [
        (503, {"error": "upstream_timeout", "retryable": True}, True),
        (503, {"error": "upstream_timeout", "retryable": False}, False),
        (503, {"error": "failed"}, False),
        (503, ["retryable"], False),
        (500, {"error": "upstream_timeout", "retryable": True}, False),
    ],
)
def test_only_a_503_marked_retryable_is_a_read_a_later_attempt_may_answer(status, body, retryable):
    with _bank(body, status=status) as base_url, pytest.raises(BankReadError) as raised:
        read_body(base_url, "/v1/cases")

    assert isinstance(raised.value, BankUnavailable) is retryable


def test_a_503_whose_body_is_not_json_is_not_retryable(monkeypatch):
    class Response:
        status = 503

        def read(self):
            return b"Service Unavailable"

    class Gateway:
        def __init__(self, host, port, timeout=None):
            return

        def request(self, method, path):
            return

        def getresponse(self):
            return Response()

        def close(self):
            return

    monkeypatch.setattr("src.load_records.HTTPConnection", Gateway)

    with pytest.raises(BankReadError) as raised:
        read_body("http://127.0.0.1:8765", "/v1/cases")

    assert not isinstance(raised.value, BankUnavailable)


def test_a_dropped_connection_is_a_read_a_later_attempt_may_answer():
    with pytest.raises(BankUnavailable):
        read_body(_closed_bank(), "/v1/cases")


def test_a_bank_that_never_answers_is_a_read_a_later_attempt_may_answer():
    release = threading.Event()

    class Silent(BaseHTTPRequestHandler):
        def do_GET(self):
            release.wait(timeout=5)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Silent)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    started = time.monotonic()
    try:
        with pytest.raises(BankUnavailable):
            read_body(f"http://{host}:{port}", "/v1/cases", timeout=0.2)
        assert time.monotonic() - started < 2.0
    finally:
        release.set()
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def _closed_bank():
    server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    host, port = server.server_address
    server.server_close()
    return f"http://{host}:{port}"


@contextmanager
def _bank(body, status=200):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/v1/cases":
                self.send_error(404)
                return
            raw = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
