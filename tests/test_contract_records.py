"""Contract objects read from the bank, one per case.

The fake bank records every request path, so a tool read that did not happen is
visible here. Expected values come from the policy files, the documents and the
supplied gold answer, not from the runner's own arithmetic.
"""

import json
import runpy
import shutil
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from src.contract_records import (
    ContractRecordError,
    load_contract_records,
    load_contract_results,
    main,
)

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "data" / "dev"

CARD_D01 = {
    "case_id": "CARD-D01",
    "intake_source": "CARD-D01-INTAKE",
    "documents": ["CARD-D01-INTAKE", "CARD-D01-ATTACHMENT"],
}
CARD_D11 = {
    "case_id": "CARD-D11",
    "intake_source": "CARD-D11-INTAKE",
    "documents": ["CARD-D11-INTAKE", "CARD-D11-ATTACHMENT"],
}
CARD_D04 = {
    "case_id": "CARD-D04",
    "intake_source": "CARD-D04-INTAKE",
    "documents": ["CARD-D04-INTAKE", "CARD-D04-ATTACHMENT"],
}
CARD_D12 = {
    "case_id": "CARD-D12",
    "intake_source": "CARD-D12-INTAKE",
    "documents": ["CARD-D12-INTAKE", "CARD-D12-ATTACHMENT"],
}

TRANSACTIONS = "/v1/cases/CARD-D01/transactions"
MERCHANT = "/v1/cases/CARD-D01/merchant"

TOOL_BODIES = {
    TRANSACTIONS: {
        "source_id": "CARD-D01-TRANSACTIONS",
        "transactions": [
            {
                "transaction_id": "TX-D01",
                "amount": 117,
                "currency": "XCR",
                "merchant_id": "MER-MORROW",
                "posted_date": "2026-08-19",
            }
        ],
    },
    MERCHANT: {
        "source_id": "CARD-D01-MERCHANT",
        "merchant_id": "MER-MORROW",
        "display_name": "Morrow Supplies",
        "note": (
            "Morrow Supplies sells home services and supplies. "
            "Merchant category: general services."
        ),
        "private_token": "SYNTHETIC-PRIVATE-CARD-D01",
    },
}

CARD_D01_CONTRACT = {
    "case_id": "CARD-D01",
    "classification": "unauthorized",
    "routing": "ready_for_review",
    "policy_ids": ["CARD-POLICY-V2", "CARD-PROCEDURE-01"],
    "facts": {
        "transaction_id": "TX-D01",
        "amount": 117,
        "currency": "XCR",
        "reported_date": "2026-10-01",
    },
    "missing_information": [],
    "deadline": "2026-10-31",
    "citations": [
        {
            "claim": "customer_evidence",
            "source_id": "CARD-D01-INTAKE",
            "quote": (
                "I found a card purchase at Morrow Supplies for 117 crowns. "
                "I do not recognize it and need help checking it."
            ),
        },
        {
            "claim": "customer_evidence",
            "source_id": "CARD-D01-ATTACHMENT",
            "quote": "Amount: 117 XCR",
        },
        {
            "claim": "transaction_record",
            "source_id": "CARD-D01-TRANSACTIONS",
            "quote": (
                '{"amount": 117, "currency": "XCR", "merchant_id": "MER-MORROW", '
                '"posted_date": "2026-08-19", "transaction_id": "TX-D01"}'
            ),
        },
        {
            "claim": "classification",
            "source_id": "CARD-PROCEDURE-01",
            "quote": (
                "Use unauthorized when the customer denies authorizing the named card "
                "purchase; if confirmation is absent,\n"
                "use the provisional unauthorized classification and request "
                "authorization_confirmation."
            ),
        },
        {
            "claim": "routing",
            "source_id": "CARD-PROCEDURE-01",
            "quote": (
                "Routing precedence: manual_review for unsupported/ambiguous cases or "
                "unavailable transaction service;\n"
                "otherwise request_information if required evidence is missing; "
                "otherwise ready_for_review."
            ),
        },
        {
            "claim": "deadline",
            "source_id": "CARD-POLICY-V2",
            "quote": "Unauthorized deadline days: 30",
        },
    ],
    "follow_up_questions": [],
    "narrative": (
        "Draft for human review: CARD-D01 is classified unauthorized and routed "
        "ready_for_review, with a policy deadline of 2026-10-31; no case has been created."
    ),
}


def test_card_d01_contract_is_emitted_from_the_bank_and_the_dataset():
    with _bank({"cases": [CARD_D01]}, TOOL_BODIES) as (base_url, seen):
        result = load_contract_records(base_url, DEV)

    assert result == [CARD_D01_CONTRACT]
    assert seen == ["/v1/cases", TRANSACTIONS, MERCHANT]


def test_each_case_reads_its_own_tools_and_uses_its_own_policy_version():
    case_list = {"cases": [CARD_D01, CARD_D11]}
    tool_bodies = {
        TRANSACTIONS: TOOL_BODIES[TRANSACTIONS],
        MERCHANT: TOOL_BODIES[MERCHANT],
        "/v1/cases/CARD-D11/transactions": {
            "source_id": "CARD-D11-TRANSACTIONS",
            "transactions": [
                {
                    "transaction_id": "TX-D11",
                    "amount": 287,
                    "currency": "XCR",
                    "merchant_id": "MER-MORROW",
                    "posted_date": "2026-08-19",
                }
            ],
        },
        "/v1/cases/CARD-D11/merchant": TOOL_BODIES[MERCHANT],
    }

    with _bank(case_list, tool_bodies) as (base_url, seen):
        result = load_contract_records(base_url, DEV)

    assert [contract["case_id"] for contract in result] == ["CARD-D01", "CARD-D11"]
    assert [contract["policy_ids"] for contract in result] == [
        ["CARD-POLICY-V2", "CARD-PROCEDURE-01"],
        ["CARD-POLICY-V1", "CARD-PROCEDURE-01"],
    ]
    assert [contract["deadline"] for contract in result] == ["2026-10-31", "2026-09-20"]
    assert [contract["facts"]["amount"] for contract in result] == [117, 287]
    assert seen == [
        "/v1/cases",
        TRANSACTIONS,
        MERCHANT,
        "/v1/cases/CARD-D11/transactions",
        "/v1/cases/CARD-D11/merchant",
    ]


def test_the_private_merchant_token_never_reaches_the_contract():
    with _bank({"cases": [CARD_D01]}, TOOL_BODIES) as (base_url, _seen):
        result = load_contract_records(base_url, DEV)

    emitted = json.dumps(result)
    assert "SYNTHETIC-PRIVATE-CARD-D01" not in emitted
    assert "CUST-D01" not in emitted


def test_a_failed_transaction_read_stops_the_case():
    with _bank({"cases": [CARD_D01]}, TOOL_BODIES, statuses={TRANSACTIONS: 503}) as (
        base_url,
        seen,
    ):
        with pytest.raises(ContractRecordError):
            load_contract_records(base_url, DEV)

    assert seen == ["/v1/cases", TRANSACTIONS]


def test_a_failed_merchant_read_stops_the_case():
    with _bank({"cases": [CARD_D01]}, TOOL_BODIES, statuses={MERCHANT: 404}) as (
        base_url,
        seen,
    ):
        with pytest.raises(ContractRecordError):
            load_contract_records(base_url, DEV)

    assert seen == ["/v1/cases", TRANSACTIONS, MERCHANT]


def test_a_transaction_body_without_an_amount_is_rejected():
    tool_bodies = {
        **TOOL_BODIES,
        TRANSACTIONS: {
            "source_id": "CARD-D01-TRANSACTIONS",
            "transactions": [
                {
                    "transaction_id": "TX-D01",
                    "currency": "XCR",
                    "merchant_id": "MER-MORROW",
                    "posted_date": "2026-08-19",
                }
            ],
        },
    }

    with _bank({"cases": [CARD_D01]}, tool_bodies) as (base_url, _seen):
        with pytest.raises(ContractRecordError):
            load_contract_records(base_url, DEV)


def test_a_merchant_body_without_a_note_is_rejected():
    tool_bodies = {
        **TOOL_BODIES,
        MERCHANT: {
            "source_id": "CARD-D01-MERCHANT",
            "merchant_id": "MER-MORROW",
            "display_name": "Morrow Supplies",
        },
    }

    with _bank({"cases": [CARD_D01]}, tool_bodies) as (base_url, _seen):
        with pytest.raises(ContractRecordError):
            load_contract_records(base_url, DEV)


def test_a_reported_date_outside_every_policy_window_stops_before_the_tools(tmp_path):
    dataset = _dataset(tmp_path)
    (dataset / "documents" / "LATE-INTAKE.md").write_text(
        "Source ID: LATE-INTAKE\n"
        "Reported date: 2027-01-01\n"
        "Authorization: denied\n"
        "The purchase was not mine.\n"
    )
    case_list = {
        "cases": [
            {
                "case_id": "LATE",
                "intake_source": "LATE-INTAKE",
                "documents": ["LATE-INTAKE", "LATE-ATTACHMENT"],
            }
        ]
    }

    with _bank(case_list, {}) as (base_url, seen):
        with pytest.raises(ContractRecordError):
            load_contract_records(base_url, dataset)

    assert seen == ["/v1/cases"]


def test_a_case_without_a_paired_attachment_name_stops_before_the_tools(tmp_path):
    dataset = _dataset(tmp_path)
    (dataset / "documents" / "ODD.md").write_text(
        "Source ID: ODD\n"
        "Reported date: 2026-10-01\n"
        "Authorization: denied\n"
        "The purchase was not mine.\n"
    )
    case_list = {
        "cases": [
            {"case_id": "ODD", "intake_source": "ODD", "documents": ["ODD"]},
        ]
    }

    with _bank(case_list, {}) as (base_url, seen):
        with pytest.raises(ContractRecordError):
            load_contract_records(base_url, dataset)

    assert seen == ["/v1/cases"]


def test_a_missing_attachment_file_stops_before_the_tools(tmp_path):
    dataset = tmp_path / "data"
    shutil.copytree(DEV, dataset)
    (dataset / "documents" / "CARD-D01-ATTACHMENT.md").unlink()

    with _bank({"cases": [CARD_D01]}, {}) as (base_url, seen):
        with pytest.raises(ContractRecordError):
            load_contract_records(base_url, dataset)

    assert seen == ["/v1/cases"]


def test_an_attachment_without_an_amount_line_stops_after_the_tool_reads(tmp_path):
    dataset = tmp_path / "data"
    shutil.copytree(DEV, dataset)
    (dataset / "documents" / "CARD-D01-ATTACHMENT.md").write_text(
        "Source ID: CARD-D01-ATTACHMENT\nMerchant: Morrow Supplies\n"
    )

    with _bank({"cases": [CARD_D01]}, TOOL_BODIES) as (base_url, seen):
        with pytest.raises(ContractRecordError):
            load_contract_records(base_url, dataset)

    assert seen == ["/v1/cases", TRANSACTIONS, MERCHANT]


def test_a_case_that_cannot_be_built_does_not_stop_the_cases_after_it():
    case_list = {"cases": [CARD_D01, CARD_D11]}

    with _bank(case_list, _d01_and_d11_bodies(), statuses={TRANSACTIONS: 503}) as (
        base_url,
        seen,
    ):
        results = load_contract_results(base_url, DEV)

    assert [result["case_id"] for result in results] == ["CARD-D01", "CARD-D11"]
    assert results[0]["contract"] is None
    assert results[0]["error"] == "BankReadError"
    assert results[1]["error"] is None
    assert results[1]["contract"] is not None
    assert results[1]["contract"]["deadline"] == "2026-09-20"
    assert seen == [
        "/v1/cases",
        TRANSACTIONS,
        "/v1/cases/CARD-D11/transactions",
        "/v1/cases/CARD-D11/merchant",
    ]


def test_the_reason_is_the_applications_own_message_when_there_is_one(tmp_path):
    dataset = tmp_path / "data"
    shutil.copytree(DEV, dataset)
    (dataset / "documents" / "CARD-D01-ATTACHMENT.md").write_text(
        "Source ID: CARD-D01-ATTACHMENT\nMerchant: Morrow Supplies\n"
    )

    with _bank({"cases": [CARD_D01]}, TOOL_BODIES) as (base_url, _seen):
        results = load_contract_results(base_url, dataset)

    assert results == [
        {
            "case_id": "CARD-D01",
            "contract": None,
            "error": "expected exactly one 'Amount:' line in the source",
        }
    ]


def test_the_reason_never_copies_a_rejected_payload():
    tool_bodies = {
        **TOOL_BODIES,
        MERCHANT: {
            "source_id": "CARD-D01-MERCHANT",
            "merchant_id": "MER-MORROW",
            "display_name": "Morrow Supplies",
            "private_token": "SYNTHETIC-PRIVATE-CARD-D01",
        },
    }

    with _bank({"cases": [CARD_D01]}, tool_bodies) as (base_url, _seen):
        results = load_contract_results(base_url, DEV)

    assert results[0]["error"] == "ValidationError"
    assert "SYNTHETIC-PRIVATE" not in json.dumps(results)


def test_load_contract_records_names_the_case_that_could_not_be_built():
    case_list = {"cases": [CARD_D01, CARD_D11]}

    with _bank(case_list, _d01_and_d11_bodies(), statuses={TRANSACTIONS: 503}) as (
        base_url,
        _seen,
    ):
        with pytest.raises(ContractRecordError, match="^CARD-D01: BankReadError$"):
            load_contract_records(base_url, DEV)


def test_main_prints_every_built_contract_and_names_the_rest(capsys, monkeypatch):
    case_list = {"cases": [CARD_D01, CARD_D11]}

    with _bank(case_list, _d01_and_d11_bodies(), statuses={TRANSACTIONS: 503}) as (
        base_url,
        _seen,
    ):
        monkeypatch.setattr(sys, "argv", ["contract_records", base_url, str(DEV)])
        with pytest.raises(SystemExit) as stopped:
            main()

    printed = capsys.readouterr()
    assert stopped.value.code == 1
    assert [contract["case_id"] for contract in json.loads(printed.out)] == ["CARD-D11"]
    assert printed.err == "CARD-D01: not built: BankReadError\n"


def test_main_exits_normally_when_every_case_is_built(capsys, monkeypatch):
    with _bank({"cases": [CARD_D01]}, TOOL_BODIES) as (base_url, _seen):
        monkeypatch.setattr(sys, "argv", ["contract_records", base_url, str(DEV)])
        main()

    printed = capsys.readouterr()
    assert json.loads(printed.out) == [CARD_D01_CONTRACT]
    assert printed.err == ""


def test_main_reports_an_unreadable_case_list(capsys, monkeypatch):
    with _bank({"cases": "not a list"}, {}) as (base_url, _seen):
        monkeypatch.setattr(sys, "argv", ["contract_records", base_url, str(DEV)])
        with pytest.raises(SystemExit) as stopped:
            main()

    printed = capsys.readouterr()
    assert stopped.value.code == 1
    assert printed.out == ""
    assert printed.err == "the bank case list could not be read\n"


def test_running_the_module_uses_the_local_mock_and_data_dev_by_default(capsys, monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(sys, "argv", ["contract_records"])
    monkeypatch.setattr(
        "src.load_records.HTTPConnection",
        _refusing_connection,
    )

    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(str(ROOT / "src" / "contract_records.py"), run_name="__main__")

    assert stopped.value.code == 1
    assert capsys.readouterr().err == "the bank case list could not be read\n"


class _refusing_connection:
    def __init__(self, host, port):
        assert (host, port) == ("127.0.0.1", 8765)

    def request(self, method, path):
        raise ConnectionRefusedError

    def close(self):
        return


def test_cases_with_missing_evidence_are_emitted_with_targeted_questions():
    case_list = {"cases": [CARD_D04, CARD_D12]}
    tool_bodies = {
        "/v1/cases/CARD-D04/transactions": {
            "source_id": "CARD-D04-TRANSACTIONS",
            "transactions": [
                {
                    "transaction_id": "TX-D04",
                    "amount": 168,
                    "currency": "XCR",
                    "merchant_id": "MER-MORROW",
                    "posted_date": "2026-08-19",
                }
            ],
        },
        "/v1/cases/CARD-D04/merchant": {
            "source_id": "CARD-D04-MERCHANT",
            "merchant_id": "MER-MORROW",
            "display_name": "Morrow Supplies",
            "note": (
                "Morrow Supplies sells home services and supplies. "
                "Merchant category: general services."
            ),
            "private_token": "SYNTHETIC-PRIVATE-CARD-D04",
        },
        "/v1/cases/CARD-D12/transactions": {
            "source_id": "CARD-D12-TRANSACTIONS",
            "transactions": [
                {
                    "transaction_id": "TX-D12",
                    "amount": 304,
                    "currency": "XCR",
                    "merchant_id": "MER-MORROW",
                    "posted_date": "2026-08-19",
                }
            ],
        },
        "/v1/cases/CARD-D12/merchant": {
            "source_id": "CARD-D12-MERCHANT",
            "merchant_id": "MER-MORROW",
            "display_name": "Morrow Supplies",
            "note": (
                "Morrow Supplies sells home services and supplies. "
                "Merchant category: general services."
            ),
            "private_token": "SYNTHETIC-PRIVATE-CARD-D12",
        },
    }

    with _bank(case_list, tool_bodies) as (base_url, seen):
        result = load_contract_records(base_url, DEV)

    assert [contract["case_id"] for contract in result] == ["CARD-D04", "CARD-D12"]
    assert result[0]["classification"] == "unauthorized"
    assert result[1]["classification"] == "service_not_received"
    assert [contract["routing"] for contract in result] == [
        "request_information",
        "request_information",
    ]
    assert result[0]["missing_information"] == ["authorization_confirmation"]
    assert result[1]["missing_information"] == [
        "promised_service_date",
        "purchase_receipt",
    ]
    assert [question["field"] for question in result[0]["follow_up_questions"]] == [
        "authorization_confirmation"
    ]
    assert [question["field"] for question in result[1]["follow_up_questions"]] == [
        "promised_service_date",
        "purchase_receipt",
    ]
    assert [contract["deadline"] for contract in result] == [
        "2026-10-31",
        "2026-12-03",
    ]
    assert seen == [
        "/v1/cases",
        "/v1/cases/CARD-D04/transactions",
        "/v1/cases/CARD-D04/merchant",
        "/v1/cases/CARD-D12/transactions",
        "/v1/cases/CARD-D12/merchant",
    ]


def _d01_and_d11_bodies():
    return {
        **TOOL_BODIES,
        "/v1/cases/CARD-D11/transactions": {
            "source_id": "CARD-D11-TRANSACTIONS",
            "transactions": [
                {
                    "transaction_id": "TX-D11",
                    "amount": 287,
                    "currency": "XCR",
                    "merchant_id": "MER-MORROW",
                    "posted_date": "2026-08-19",
                }
            ],
        },
        "/v1/cases/CARD-D11/merchant": TOOL_BODIES[MERCHANT],
    }


def _dataset(tmp_path):
    (tmp_path / "policies").mkdir()
    for policy in (DEV / "policies").glob("*.md"):
        (tmp_path / "policies" / policy.name).write_text(policy.read_text())
    (tmp_path / "documents").mkdir()
    return tmp_path


@contextmanager
def _bank(case_list, tool_bodies, statuses=None):
    statuses = {} if statuses is None else statuses
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            if self.path == "/v1/cases":
                self._send(200, case_list)
                return
            status = statuses.get(self.path)
            if status is not None:
                self._send(status, {"error": "failed"})
                return
            body = tool_bodies.get(self.path)
            if body is None:
                self._send(404, {"error": "not_found"})
                return
            self._send(200, body)

        def _send(self, status, body):
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
        yield f"http://{host}:{port}", seen
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_a_case_that_names_evidence_this_step_cannot_read_is_not_built():
    case_list = {
        "cases": [
            {
                **CARD_D01,
                "documents": [*CARD_D01["documents"], "CARD-D01-FOLLOWUP"],
            }
        ]
    }

    with _bank(case_list, TOOL_BODIES) as (base_url, seen):
        results = load_contract_results(base_url, DEV)

    assert results == [
        {
            "case_id": "CARD-D01",
            "contract": None,
            "error": "the case names evidence this step cannot read: CARD-D01-FOLLOWUP",
        }
    ]
    assert seen == ["/v1/cases"]
