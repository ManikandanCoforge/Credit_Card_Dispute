"""Conflicting customer accounts and cash withdrawals go to a human.

Expected values come from CARD-PROCEDURE-01, the policy files, the case
documents and the supplied gold answers for CARD-D05 and CARD-D06.
"""

import json
import re
from pathlib import Path

import pytest

from src.build_records import build_complaint_records
from src.contract import ContractError, assemble_contract
from src.escalation import find_escalation

DEV = Path(__file__).resolve().parents[1] / "data" / "dev"
PROCEDURE_TEXT = (DEV / "policies" / "CARD-PROCEDURE-01.md").read_text(encoding="utf-8")
POLICY_TEXT = (DEV / "policies" / "CARD-POLICY-V2.md").read_text(encoding="utf-8")
PROMISES = re.compile(
    r"refund|reimburs|guarantee|eligib|approved|success|will be (?:credited|returned)",
    re.IGNORECASE,
)


def test_card_d05_conflicting_statements_are_ambiguous_with_both_sides_cited():
    result, sources = _assemble_dev("CARD-D05", 185, ["CARD-D05-FOLLOWUP"])

    assert result["classification"] == "ambiguous"
    assert result["routing"] == "manual_review"
    assert result["deadline"] is None
    assert result["policy_ids"] == ["CARD-POLICY-V2", "CARD-PROCEDURE-01"]
    assert result["facts"] == {
        "transaction_id": "TX-D05",
        "amount": 185,
        "currency": "XCR",
        "reported_date": "2026-10-02",
    }
    assert result["missing_information"] == []
    assert result["follow_up_questions"] == []
    conflict = [c for c in result["citations"] if c["claim"].startswith("authorization_")]
    assert conflict == [
        {
            "claim": "authorization_denied",
            "source_id": "CARD-D05-INTAKE",
            "quote": "I do not recognize it and need help checking it.",
        },
        {
            "claim": "authorization_confirmed",
            "source_id": "CARD-D05-FOLLOWUP",
            "quote": "I did authorize this purchase after all.",
        },
    ]
    assert {
        "claim": "ambiguous_rule",
        "source_id": "CARD-PROCEDURE-01",
        "quote": (
            "If customer accounts conflict about authorization, classification is "
            "ambiguous; deadline is null."
        ),
    } in result["citations"]
    _assert_exact_quotes(result, sources)


def test_card_d05_narrative_states_the_conflict_without_resolving_it():
    result, _sources = _assemble_dev("CARD-D05", 185, ["CARD-D05-FOLLOWUP"])

    narrative = result["narrative"]
    assert narrative.startswith("Draft for human review:")
    assert "Denied in CARD-D05-INTAKE; confirmed in CARD-D05-FOLLOWUP." in narrative
    assert "does not decide which statement is correct" in narrative
    assert "No case has been created." in narrative
    assert PROMISES.search(narrative) is None


def test_card_d06_cash_withdrawal_is_unsupported_and_keeps_its_facts():
    result, sources = _assemble_dev("CARD-D06", 202)

    assert result["classification"] == "unsupported"
    assert result["routing"] == "manual_review"
    assert result["deadline"] is None
    assert result["policy_ids"] == ["CARD-POLICY-V2", "CARD-PROCEDURE-01"]
    assert result["facts"] == {
        "transaction_id": "TX-D06",
        "amount": 202,
        "currency": "XCR",
        "reported_date": "2026-10-03",
    }
    claims = [citation["claim"] for citation in result["citations"]]
    assert claims == [
        "customer_evidence",
        "customer_evidence",
        "transaction_record",
        "cash_withdrawal",
        "unsupported_rule",
        "routing",
        "policy_selection",
        "policy_selection",
    ]
    assert result["citations"][3]["quote"] == "My ATM withdrawal for 202 crowns did not dispense cash."
    assert "no other classification is assigned" in result["narrative"]
    assert PROMISES.search(result["narrative"]) is None
    _assert_exact_quotes(result, sources)


def test_manual_review_outranks_missing_information_and_still_lists_the_fields():
    record = _record(authorization="not supplied", missing=["authorization_confirmation"])

    result = _assemble(record, statement="I took cash out at an ATM and none came out.")

    assert result["routing"] == "manual_review"
    assert result["missing_information"] == ["authorization_confirmation"]
    assert result["follow_up_questions"] == [
        {
            "field": "authorization_confirmation",
            "question": (
                "Can you confirm whether you authorized the card transaction named in your "
                "complaint?"
            ),
        }
    ]
    assert {
        "claim": "routing",
        "source_id": "CARD-PROCEDURE-01",
        "quote": (
            "Manual review takes precedence over missing-information routing; "
            "still list missing fields."
        ),
    } in result["citations"]
    assert "Missing information is still requested: authorization_confirmation." in (
        result["narrative"]
    )


@pytest.mark.parametrize(
    "statement",
    [
        "My ATM withdrawal for 90 crowns did not dispense cash.",
        "I withdrew 90 crowns in cash and the machine gave me nothing.",
        "The cash machine kept my money.",
        "A cash withdrawal of 90 crowns appeared twice.",
        "The atm never dispensed the notes.",
    ],
)
def test_a_cash_withdrawal_in_any_wording_is_unsupported(statement):
    assert _assemble(_record(), statement=statement)["classification"] == "unsupported"


@pytest.mark.parametrize(
    "statement",
    [
        "I found a card purchase I do not recognize.",
        "I paid for a service that never arrived.",
        "The merchant charged me twice for one purchase.",
    ],
)
def test_a_card_purchase_is_not_escalated(statement):
    escalation = find_escalation(
        _intake(statement, authorization="denied"), [], PROCEDURE_TEXT
    )

    assert escalation is None


def test_form_lines_alone_can_conflict():
    followup = "# Customer follow-up email\n\nSource ID: TEST-FOLLOWUP\n\nAuthorization: confirmed\n"

    result = _assemble(_record(), statement="Please look at this charge.", customer_texts=[followup])

    assert result["classification"] == "ambiguous"
    assert [c["quote"] for c in result["citations"] if c["claim"].startswith("authorization_")] == [
        "Authorization: denied",
        "Authorization: confirmed",
    ]


def test_one_intake_that_confirms_on_the_form_and_denies_in_prose_is_ambiguous():
    record = _record(authorization="confirmed")

    result = _assemble(
        record, statement="I did not authorize this charge.", authorization="confirmed"
    )

    assert result["classification"] == "ambiguous"
    assert {c["source_id"] for c in result["citations"] if c["claim"].startswith("authorization_")} == {
        "TEST-INTAKE"
    }


def test_two_customer_statements_that_agree_are_not_escalated():
    followup = (
        "# Customer follow-up email\n\nSource ID: TEST-FOLLOWUP\n\n"
        "I still do not recognize this purchase.\nAuthorization: denied\n"
    )

    escalation = find_escalation(
        _intake("I found a purchase I do not recognize.", authorization="denied"),
        [followup],
        PROCEDURE_TEXT,
    )

    assert escalation is None


def test_unsupported_is_reported_when_a_cash_complaint_also_conflicts():
    followup = "# Customer follow-up email\n\nSource ID: TEST-FOLLOWUP\n\nI did authorize it.\n"

    result = _assemble(
        _record(),
        statement="My ATM withdrawal failed and I do not recognize it.",
        customer_texts=[followup],
    )

    assert result["classification"] == "unsupported"


def test_headings_and_form_lines_are_not_read_as_customer_prose():
    intake = (
        "# ATM notice\n\nSource ID: TEST-INTAKE\n\nReported date: 2026-10-01\n"
        "Merchant note: cash withdrawal\nAuthorization: denied\nI do not recognize it.\n"
    )

    assert find_escalation(intake, [], PROCEDURE_TEXT) is None


@pytest.mark.parametrize(
    "procedure_text",
    [
        "Source ID: CARD-PROCEDURE-TEST\nRouting precedence: manual_review first;\n",
        "Source ID: CARD-PROCEDURE-TEST\nCash withdrawal disputes are unsupported\n",
    ],
)
def test_a_procedure_without_the_escalation_rule_sentence_is_rejected(procedure_text):
    with pytest.raises(ContractError):
        _assemble(_record(), statement="My ATM withdrawal failed.", procedure_text=procedure_text)


def test_a_customer_statement_without_a_source_id_is_rejected():
    followup = "# Customer follow-up email\n\nI did authorize this purchase after all.\n"

    with pytest.raises(ContractError):
        _assemble(_record(), statement="I do not recognize it.", customer_texts=[followup])


def test_an_escalated_record_without_a_policy_version_is_rejected():
    record = _record()
    record["policy"] = {"version_id": None, "procedure_id": None}

    with pytest.raises(ContractError):
        _assemble(record, statement="My ATM withdrawal failed.")


def _assert_exact_quotes(result, sources):
    for citation in result["citations"]:
        assert citation["quote"] in sources[citation["source_id"]]
        assert "\n" not in citation["quote"]


def _assemble_dev(case_id, amount, extra=()):
    record = build_complaint_records(
        [{"case_id": case_id, "intake_source": f"{case_id}-INTAKE"}], DEV
    )[0]
    body = {
        "source_id": f"{case_id}-TRANSACTIONS",
        "transactions": [
            {
                "transaction_id": f"TX-{case_id[5:]}",
                "amount": amount,
                "currency": "XCR",
                "merchant_id": "MER-MORROW",
                "posted_date": "2026-08-19",
            }
        ],
    }
    record["transactions"] = body["transactions"]
    documents = {
        source_id: (DEV / "documents" / f"{source_id}.md").read_text(encoding="utf-8")
        for source_id in [f"{case_id}-INTAKE", f"{case_id}-ATTACHMENT", *extra]
    }
    sources = {
        **documents,
        "CARD-PROCEDURE-01": PROCEDURE_TEXT,
        "CARD-POLICY-V2": POLICY_TEXT,
        f"{case_id}-TRANSACTIONS": json.dumps(body, sort_keys=True),
    }
    result = assemble_contract(
        record,
        intake_text=documents[f"{case_id}-INTAKE"],
        attachment_text=documents[f"{case_id}-ATTACHMENT"],
        procedure_text=PROCEDURE_TEXT,
        policy_text=POLICY_TEXT,
        transactions_text=sources[f"{case_id}-TRANSACTIONS"],
        customer_texts=[documents[source_id] for source_id in extra],
    )
    return result, sources


def _assemble(
    record,
    statement,
    authorization="denied",
    customer_texts=(),
    procedure_text=PROCEDURE_TEXT,
):
    record["intake"]["statement"] = statement
    return assemble_contract(
        record,
        intake_text=_intake(statement, authorization),
        attachment_text="Source ID: TEST-ATTACHMENT\nAmount: 90 XCR\n",
        procedure_text=procedure_text,
        policy_text=POLICY_TEXT,
        transactions_text=json.dumps(
            {"source_id": "TEST-TRANSACTIONS", "transactions": record["transactions"]},
            sort_keys=True,
        ),
        customer_texts=list(customer_texts),
    )


def _intake(statement, authorization):
    return (
        "# Customer complaint and intake form\n\nSource ID: TEST-INTAKE\n\n"
        f"{statement}\n\nReported date: 2026-10-01\nTransaction ID: TX-TEST\n"
        f"Authorization: {authorization}\n"
    )


def _record(authorization="denied", missing=None):
    return {
        "case_id": "TEST-CASE",
        "intake": {
            "source_id": "TEST-INTAKE",
            "statement": "",
            "reported_date": "2026-10-01",
            "transaction_id": "TX-TEST",
            "authorization": authorization,
            "promised_service_date": "2026-08-20",
            "purchase_receipt": "attached",
            "submission_reference": "dispute-test",
        },
        "policy": {"version_id": "CARD-POLICY-V2", "procedure_id": "CARD-PROCEDURE-01"},
        "missing_information": [] if missing is None else missing,
        "routing": None,
        "transactions": [
            {
                "transaction_id": "TX-TEST",
                "amount": 90,
                "currency": "XCR",
                "merchant_id": "MER-TEST",
                "posted_date": "2026-08-19",
            }
        ],
    }
