"""The contract object assembled from one working record.

Expected values here come from docs/OUTPUT_CONTRACT.md, the policy files and the
case documents, never from the assembler's own arithmetic.
"""

import json
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict

from src.contract import ContractError, assemble_contract

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "data" / "dev"
INTAKE_TEXT = (DEV / "documents" / "CARD-D01-INTAKE.md").read_text()
ATTACHMENT_TEXT = (DEV / "documents" / "CARD-D01-ATTACHMENT.md").read_text()
PROCEDURE_TEXT = (DEV / "policies" / "CARD-PROCEDURE-01.md").read_text()
POLICY_TEXT = (DEV / "policies" / "CARD-POLICY-V2.md").read_text()
D01_CHARGE = {
    "transaction_id": "TX-D01",
    "amount": 117,
    "currency": "XCR",
    "merchant_id": "MER-MORROW",
    "posted_date": "2026-08-19",
}
# The evaluator stores a tool body as json.dumps(body, sort_keys=True).
TRANSACTIONS_TEXT = json.dumps(
    {"source_id": "CARD-D01-TRANSACTIONS", "transactions": [D01_CHARGE]}, sort_keys=True
)


class _Facts(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    transaction_id: str | None
    amount: int | None
    currency: str | None
    reported_date: str | None


class _Citation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    claim: str
    source_id: str
    quote: str


class _Question(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    field: str
    question: str


class _Contract(BaseModel):
    """docs/OUTPUT_CONTRACT.md, field for field."""

    model_config = ConfigDict(extra="forbid", strict=True)

    case_id: str
    classification: Literal[
        "unauthorized",
        "duplicate_charge",
        "service_not_received",
        "ambiguous",
        "unsupported",
    ]
    routing: Literal["ready_for_review", "request_information", "manual_review"]
    policy_ids: list[str]
    facts: _Facts
    missing_information: list[str]
    deadline: str | None
    citations: list[_Citation]
    follow_up_questions: list[_Question]
    narrative: str


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
        "Draft for human review.\n"
        "Evidence: CARD-D01 reports transaction TX-D01, reported 2026-10-01. The transaction "
        "service shows 117 XCR. Cited sources: CARD-D01-INTAKE, CARD-D01-ATTACHMENT, "
        "CARD-D01-TRANSACTIONS, CARD-PROCEDURE-01, CARD-POLICY-V2.\n"
        "Uncertainty: None found in the cited sources.\n"
        "Recommendation: classified unauthorized under CARD-POLICY-V2, CARD-PROCEDURE-01 and "
        "routed ready_for_review. The policy deadline is 2026-10-31. A reviewer can check the "
        "cited evidence and decide.\n"
        "Limitations: prepared only from the cited documents and tool data under the fictional "
        "bank procedure; no card-network or legal rules were used. No case has been created: a "
        "person must approve this exact draft first, and any change needs a new approval.\n"
        "Customer reply (DRAFT, not sent): Thank you for contacting Lumen Bank about "
        "transaction TX-D01. Your report is with our dispute team for review. We cannot "
        "confirm an outcome yet."
    ),
}


def test_card_d01_emits_exactly_the_ten_contract_fields():
    result = _assemble_card_d01()

    assert len(_Contract.model_fields) == 10
    assert list(result) == list(_Contract.model_fields)
    _Contract.model_validate(result)
    assert result == CARD_D01_CONTRACT


def test_card_d01_contract_survives_a_json_round_trip_with_numbers_as_numbers():
    emitted = json.loads(json.dumps(_assemble_card_d01()))

    assert emitted == CARD_D01_CONTRACT
    assert isinstance(emitted["facts"]["amount"], int)
    assert not isinstance(emitted["facts"]["amount"], bool)


def test_card_d01_citations_are_exact_excerpts_of_the_named_sources():
    sources = {
        "CARD-D01-INTAKE": INTAKE_TEXT,
        "CARD-D01-ATTACHMENT": ATTACHMENT_TEXT,
        "CARD-D01-TRANSACTIONS": TRANSACTIONS_TEXT,
        "CARD-PROCEDURE-01": PROCEDURE_TEXT,
        "CARD-POLICY-V2": POLICY_TEXT,
    }

    citations = _assemble_card_d01()["citations"]

    assert [citation["source_id"] for citation in citations] == [
        "CARD-D01-INTAKE",
        "CARD-D01-ATTACHMENT",
        "CARD-D01-TRANSACTIONS",
        "CARD-PROCEDURE-01",
        "CARD-PROCEDURE-01",
        "CARD-POLICY-V2",
    ]
    for citation in citations:
        assert citation["quote"] in sources[citation["source_id"]]


@pytest.mark.parametrize(
    ("reported_date", "days", "deadline"),
    [
        ("2026-10-01", 30, "2026-10-31"),
        ("2026-08-31", 20, "2026-09-20"),
        ("2026-12-31", 30, "2027-01-30"),
    ],
)
def test_the_deadline_is_the_reported_date_plus_the_policy_days(
    reported_date, days, deadline
):
    result = _assemble(
        _record(reported_date=reported_date),
        intake_text=_intake_text(reported_date),
        policy_text=_policy_text(days),
    )

    assert result["deadline"] == deadline


def test_amount_and_currency_come_from_the_named_transaction_row():
    result = _assemble(
        _record(
            transaction_id="TX-SECOND",
            transactions=[
                _charge("TX-FIRST", 11),
                _charge("TX-SECOND", 42, "EUR"),
            ],
        )
    )

    assert result["facts"] == {
        "transaction_id": "TX-SECOND",
        "amount": 42,
        "currency": "EUR",
        "reported_date": "2026-10-01",
    }


def test_an_unmatched_transaction_leaves_amount_and_currency_null():
    result = _assemble(
        _record(transaction_id="TX-MISSING", transactions=[_charge("TX-OTHER", 11)])
    )

    assert result["facts"] == {
        "transaction_id": "TX-MISSING",
        "amount": None,
        "currency": None,
        "reported_date": "2026-10-01",
    }


def test_an_absent_transaction_id_keeps_every_fact_key_and_nulls_the_amount():
    result = _assemble(
        _record(transaction_id="not supplied", transactions=[_charge("TX-ONLY", 11)])
    )

    assert result["facts"] == {
        "transaction_id": None,
        "amount": None,
        "currency": None,
        "reported_date": "2026-10-01",
    }


def test_a_working_record_without_an_intake_is_rejected():
    record = _record()
    record["intake"] = None

    with pytest.raises(ContractError):
        _assemble(record)


def test_a_confirmed_authorization_is_not_classified_by_this_step():
    with pytest.raises(ContractError):
        _assemble(_record(authorization="confirmed"))


@pytest.mark.parametrize(
    ("version_id", "procedure_id"),
    [(None, "CARD-PROCEDURE-TEST"), ("CARD-POLICY-TEST", None)],
)
def test_a_record_without_both_policy_ids_is_rejected(version_id, procedure_id):
    with pytest.raises(ContractError):
        _assemble(_record(version_id=version_id, procedure_id=procedure_id))


def test_a_record_without_a_reported_date_is_rejected():
    with pytest.raises(ContractError):
        _assemble(_record(reported_date="not supplied"))


def test_missing_required_information_is_rejected_until_questions_exist():
    with pytest.raises(ContractError):
        _assemble(_record(missing_information=["authorization_confirmation"]))


def test_an_intake_statement_that_is_not_in_the_intake_is_rejected():
    with pytest.raises(ContractError):
        _assemble(_record(statement="not supplied"))


def test_an_attachment_without_an_amount_line_is_rejected():
    with pytest.raises(ContractError):
        _assemble(_record(), attachment_text="Source ID: TEST-ATTACHMENT\nMerchant: TEST\n")


def test_a_source_without_a_source_id_is_rejected():
    with pytest.raises(ContractError):
        _assemble(_record(), attachment_text="Source ID:\nAmount: 117 XCR\n")


def test_a_policy_without_the_unauthorized_deadline_line_is_rejected():
    with pytest.raises(ContractError):
        _assemble(_record(), policy_text="Source ID: CARD-POLICY-TEST\n")


def test_a_policy_with_a_non_numeric_deadline_is_rejected():
    with pytest.raises(ContractError):
        _assemble(
            _record(), policy_text="Source ID: CARD-POLICY-TEST\nUnauthorized deadline days: thirty\n"
        )


def test_a_procedure_without_the_unauthorized_rule_is_rejected():
    with pytest.raises(ContractError):
        _assemble(_record(), procedure_text=_PROCEDURE_HEADER + _ROUTING_RULE)


def test_a_procedure_without_the_routing_rule_is_rejected():
    with pytest.raises(ContractError):
        _assemble(_record(), procedure_text=_PROCEDURE_HEADER + _UNAUTHORIZED_RULE)


def test_a_procedure_rule_without_a_full_stop_is_rejected():
    with pytest.raises(ContractError):
        _assemble(
            _record(),
            procedure_text=(
                _PROCEDURE_HEADER
                + "Use unauthorized when the customer denies authorizing the named purchase\n"
            ),
        )


def test_the_named_charge_is_cited_as_one_sorted_object_from_the_tool_body():
    charges = [_charge("TX-FIRST", 11), _charge("TX-SECOND", 42, "EUR")]
    text = _transactions_text(charges)

    result = _assemble(_record(transaction_id="TX-SECOND", transactions=charges))

    citation = result["citations"][2]
    assert citation == {
        "claim": "transaction_record",
        "source_id": "TEST-TRANSACTIONS",
        "quote": (
            '{"amount": 42, "currency": "EUR", "merchant_id": "MER-TEST", '
            '"posted_date": "2026-08-19", "transaction_id": "TX-SECOND"}'
        ),
    }
    assert citation["quote"] in text


def test_an_unmatched_transaction_cites_only_that_the_tool_was_read():
    result = _assemble(
        _record(transaction_id="TX-MISSING", transactions=[_charge("TX-OTHER", 11)])
    )

    assert result["citations"][2] == {
        "claim": "transaction_service_checked",
        "source_id": "TEST-TRANSACTIONS",
        "quote": '"source_id": "TEST-TRANSACTIONS"',
    }


@pytest.mark.parametrize(
    "transactions_text",
    [
        "not json",
        "[]",
        '{"transactions": []}',
        '{"source_id": "TEST-TRANSACTIONS"}',
        '{"source_id": 7, "transactions": []}',
        '{"source_id": "TEST-TRANSACTIONS", "transactions": {}}',
    ],
)
def test_a_transactions_body_that_is_not_usable_is_rejected(transactions_text):
    with pytest.raises(ContractError):
        _assemble(_record(), transactions_text=transactions_text)


def test_a_transactions_body_without_sorted_keys_is_rejected():
    unsorted = json.dumps(
        {
            "transactions": [
                {
                    "transaction_id": "TX-TEST",
                    "amount": 11,
                    "currency": "XCR",
                    "merchant_id": "MER-TEST",
                    "posted_date": "2026-08-19",
                }
            ],
            "source_id": "TEST-TRANSACTIONS",
        }
    )

    with pytest.raises(ContractError):
        _assemble(_record(transactions=[_charge("TX-TEST", 11)]), transactions_text=unsorted)


def _assemble_card_d01():
    return _assemble(
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
            "transactions": [D01_CHARGE],
        },
        intake_text=INTAKE_TEXT,
        attachment_text=ATTACHMENT_TEXT,
        procedure_text=PROCEDURE_TEXT,
        policy_text=POLICY_TEXT,
        transactions_text=TRANSACTIONS_TEXT,
    )


def _assemble(
    record,
    intake_text=None,
    attachment_text=None,
    procedure_text=None,
    policy_text=None,
    transactions_text=None,
):
    return assemble_contract(
        record,
        intake_text=_intake_text("2026-10-01") if intake_text is None else intake_text,
        attachment_text=_ATTACHMENT_TEXT if attachment_text is None else attachment_text,
        procedure_text=_PROCEDURE_TEXT if procedure_text is None else procedure_text,
        policy_text=_policy_text(30) if policy_text is None else policy_text,
        transactions_text=(
            _transactions_text(record.get("transactions", []))
            if transactions_text is None
            else transactions_text
        ),
    )


def _transactions_text(charges):
    return json.dumps({"source_id": "TEST-TRANSACTIONS", "transactions": charges}, sort_keys=True)


def _record(
    reported_date="2026-10-01",
    authorization="denied",
    transaction_id="TX-TEST",
    statement="The purchase was not mine.",
    version_id="CARD-POLICY-TEST",
    procedure_id="CARD-PROCEDURE-TEST",
    transactions=None,
    missing_information=None,
):
    return {
        "case_id": "TEST-CASE",
        "intake": {
            "source_id": "TEST-INTAKE",
            "statement": statement,
            "reported_date": reported_date,
            "transaction_id": transaction_id,
            "authorization": authorization,
            "promised_service_date": "2026-08-20",
            "purchase_receipt": "attached",
            "submission_reference": "dispute-test",
        },
        "policy": {"version_id": version_id, "procedure_id": procedure_id},
        "missing_information": [] if missing_information is None else missing_information,
        "routing": None,
        "transactions": [] if transactions is None else transactions,
    }


def _charge(transaction_id, amount, currency="XCR"):
    return {
        "transaction_id": transaction_id,
        "amount": amount,
        "currency": currency,
        "merchant_id": "MER-TEST",
        "posted_date": "2026-08-19",
    }


def _intake_text(reported_date):
    return (
        "Source ID: TEST-INTAKE\n"
        "Authorization: denied\n"
        f"Reported date: {reported_date}\n"
        "The purchase was not mine.\n"
    )


def _policy_text(days):
    return f"Source ID: CARD-POLICY-TEST\nUnauthorized deadline days: {days}\n"


_ATTACHMENT_TEXT = "Source ID: TEST-ATTACHMENT\nAmount: 117 XCR\n"
_PROCEDURE_HEADER = "Source ID: CARD-PROCEDURE-TEST\n"
_UNAUTHORIZED_RULE = (
    "Use unauthorized when the customer denies authorizing the named card purchase; "
    "if confirmation is absent,\n"
    "use the provisional unauthorized classification and request authorization_confirmation.\n"
)
_ROUTING_RULE = (
    "Routing precedence: manual_review for unsupported/ambiguous cases or unavailable "
    "transaction service;\n"
    "otherwise request_information if required evidence is missing; otherwise "
    "ready_for_review.\n"
)
_PROCEDURE_TEXT = _PROCEDURE_HEADER + _UNAUTHORIZED_RULE + _ROUTING_RULE


def test_a_transaction_row_with_a_field_outside_the_contract_is_rejected():
    charge = {**_charge("TX-TEST", 11), "private_token": "SYNTHETIC-PRIVATE-CARD-TEST"}
    text = json.dumps(
        {"source_id": "TEST-TRANSACTIONS", "transactions": [charge]}, sort_keys=True
    )

    with pytest.raises(ContractError) as raised:
        _assemble(
            _record(transaction_id="TX-TEST", transactions=[_charge("TX-TEST", 11)]),
            transactions_text=text,
        )

    assert "SYNTHETIC-PRIVATE" not in str(raised.value)
