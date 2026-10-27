"""The complaint script prints working records as JSON."""

import json
import runpy
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from src.app import main

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "data" / "dev"

CARD_D01 = {
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


def test_main_prints_working_records_for_the_given_bank(capsys, monkeypatch):
    with _bank(_card_d01_case_list()) as base_url:
        monkeypatch.setattr(sys, "argv", ["app", base_url, str(DEV)])
        main()

    assert capsys.readouterr().out == _printed([CARD_D01])


def test_main_uses_the_local_mock_and_data_dev_by_default(capsys, monkeypatch):
    # The defaults are checked without binding port 8765, where the README runs the
    # mock, so the tests pass while that mock is up.
    seen = []

    def prepare(base_url, data_dir):
        seen.append((base_url, data_dir))
        return [CARD_D01]

    monkeypatch.setattr("src.app.prepare_complaints", prepare)
    monkeypatch.setattr(sys, "argv", ["app"])
    main()

    assert seen == [("http://127.0.0.1:8765", "data/dev")]
    assert capsys.readouterr().out == _printed([CARD_D01])


def test_running_the_app_module_prints_working_records(capsys, monkeypatch):
    with _bank(_card_d01_case_list()) as base_url:
        monkeypatch.setattr(sys, "argv", ["src.app", base_url, str(DEV)])
        runpy.run_path(str(ROOT / "src" / "app.py"), run_name="__main__")

    assert capsys.readouterr().out == _printed([CARD_D01])


def _printed(records):
    return json.dumps(records, indent=2) + "\n"


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


@contextmanager
def _bank(body):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/v1/cases":
                self.send_error(404)
                return
            raw = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, bound_port = server.server_address
    try:
        yield f"http://{host}:{bound_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
