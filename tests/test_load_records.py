import json
import ssl
import subprocess
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from src.app import prepare_complaints
from src.load_records import CaseListError, load_complaint_records

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


def test_http_url_without_a_port_loads_the_case_list_on_port_80():
    with _bank(_card_d01_case_list(), port=80, include_port=False) as base_url:
        assert base_url == "http://127.0.0.1"
        result = load_complaint_records(base_url, DEV)

    assert result[0]["case_id"] == "CARD-D01"
    assert result[0]["intake"]["transaction_id"] == "TX-D01"
    assert result[0]["policy"]["procedure_id"] == "CARD-PROCEDURE-01"


def test_https_url_without_a_port_loads_the_case_list_on_port_443(monkeypatch, tmp_path):
    cert, key = _localhost_cert(tmp_path)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    monkeypatch.setenv("SSL_CERT_FILE", str(cert))

    with _bank(
        _card_d01_case_list(),
        port=443,
        include_port=False,
        scheme="https",
        ssl_context=context,
    ) as base_url:
        assert base_url == "https://127.0.0.1"
        result = load_complaint_records(base_url, DEV)

    assert result[0]["case_id"] == "CARD-D01"
    assert result[0]["intake"]["transaction_id"] == "TX-D01"
    assert result[0]["policy"]["procedure_id"] == "CARD-PROCEDURE-01"


def _closed_bank():
    server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    host, port = server.server_address
    server.server_close()
    return f"http://{host}:{port}"


def _card_d01_case_list():
    return {
        "cases": [
            {
                "case_id": "CARD-D01",
                "intake_source": "CARD-D01-INTAKE",
                "documents": ["CARD-D01-INTAKE", "CARD-D01-ATTACHMENT"],
            }
        ]
    }


def _localhost_cert(directory: Path) -> tuple[Path, Path]:
    cert = directory / "cert.pem"
    key = directory / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "1",
            "-nodes",
            "-subj",
            "/CN=127.0.0.1",
            "-addext",
            "subjectAltName=IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    return cert, key


@contextmanager
def _bank(body, status=200, port=0, *, include_port=True, scheme="http", ssl_context=None):
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

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    if ssl_context is not None:
        server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, bound_port = server.server_address
    authority = host if not include_port else f"{host}:{bound_port}"
    try:
        yield f"{scheme}://{authority}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
