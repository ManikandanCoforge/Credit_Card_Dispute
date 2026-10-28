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
    assert narrative.startswith("Draft for human review.")
    assert "Denied in CARD-D05-INTAKE; confirmed in CARD-D05-FOLLOWUP." in narrative
    assert "does not decide which statement is correct" in narrative
    assert "No case has been created:" in narrative
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
    """An ambiguous case requires the customer's confirmation, so a blank one is still asked."""
    record = _record(authorization="not supplied", missing=["authorization_confirmation"])
    followup = (
        "# Customer follow-up email\n\nSource ID: TEST-FOLLOWUP\n\n"
        "I did authorize this purchase after all.\n"
    )

    result = _assemble(
        record,
        statement="I do not recognize this charge.",
        authorization="not supplied",
        customer_texts=[followup],
    )

    assert (result["classification"], result["routing"]) == ("ambiguous", "manual_review")
    assert result["missing_information"] == ["authorization_confirmation"]
    assert result["follow_up_questions"] == [
        {
            "field": "authorization_confirmation",
            "question": "Can you confirm whether you authorized the named card purchase?",
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
        "The ATM did not dispense cash.",
        "I took cash out at an ATM and none came out.",
        "I tried to withdraw 90 crowns in cash and the machine gave me nothing.",
        "The cash machine kept my money.",
        "The atm never dispensed the notes.",
        # Kanit's review of 340a966: the withdrawal word before the machine, and no cash word.
        "I withdrew 200 crowns from the ATM and it gave me nothing.",
        "The ATM took my money.",
    ],
)
def test_cash_that_did_not_come_out_of_a_machine_is_unsupported(statement):
    """The procedure's case: cash withdrawn, or meant to be. How customers say it, not the regex's branches."""
    assert _assemble(_record(), statement=statement)["classification"] == "unsupported"


@pytest.mark.parametrize(
    "statement",
    [
        "I used my ATM card at Morrow Supplies. I do not recognize the charge.",
        "The merchant did not dispense the service I paid for. I do not recognize the charge.",
        "I paid cash at the shop and my card was charged as well. I do not recognize it.",
        "I found a card purchase I do not recognize.",
        "I paid for a service that never arrived.",
        "The merchant charged me twice for one purchase.",
        "I paid with my ATM card and the shop took 90 crowns.",
    ],
)
def test_a_card_purchase_that_mentions_an_atm_card_or_dispensing_is_not_escalated(statement):
    assert find_escalation(_intake(statement, authorization="denied"), [], PROCEDURE_TEXT) is None


def test_an_atm_card_purchase_stays_a_normal_unauthorized_draft():
    result = _assemble(_record(), statement="I used my ATM card at Morrow Supplies. I do not recognize the charge.")

    assert (result["classification"], result["routing"], result["deadline"]) == (
        "unauthorized",
        "ready_for_review",
        "2026-10-31",
    )


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


def test_a_heading_is_not_read_as_customer_prose():
    intake = (
        "# ATM withdrawal dispute form\n\nSource ID: TEST-INTAKE\n\nReported date: 2026-10-01\n"
        "Authorization: denied\nI do not recognize it.\n"
    )

    assert find_escalation(intake, [], PROCEDURE_TEXT) is None


def test_a_complaint_written_as_a_form_keeps_its_cash_cue():
    intake = "Source ID: TEST-INTAKE\n\nTransaction type: ATM withdrawal\nAuthorization: confirmed\n"

    escalation = find_escalation(intake, [], PROCEDURE_TEXT)

    assert escalation is not None and escalation["classification"] == "unsupported"
    assert escalation["citations"][0]["quote"] == "ATM withdrawal"


@pytest.mark.parametrize("authorization", ["denied", "confirmed"])
def test_a_cue_in_the_label_itself_is_not_lost(authorization):
    """Kanit's repro on #52: the only cash cue is the label text."""
    intake = (
        "Source ID: TEST-INTAKE\n\nCash withdrawal: the machine gave me nothing.\n"
        f"Authorization: {authorization}\n"
    )

    escalation = find_escalation(intake, [], PROCEDURE_TEXT)

    assert escalation is not None and escalation["classification"] == "unsupported"
    assert escalation["citations"][0]["quote"] == "Cash withdrawal: the machine gave me nothing."
    assert escalation["citations"][0]["quote"] in intake


def test_a_cash_label_line_escalates_the_whole_contract():
    record = _record(authorization="denied")

    result = _assemble(record, statement="Cash withdrawal: the machine gave me nothing.")

    assert (result["classification"], result["routing"], result["deadline"]) == (
        "unsupported",
        "manual_review",
        None,
    )


def test_a_plain_form_label_is_still_dropped():
    intake = "Source ID: TEST-INTAKE\n\nMerchant category: cash and carry store.\nAuthorization: denied\n"

    assert find_escalation(intake, [], PROCEDURE_TEXT) is None


def test_a_complaint_written_as_a_form_keeps_its_denial():
    intake = "Source ID: TEST-INTAKE\n\nNote: I did not authorize this charge.\nAuthorization: confirmed\n"

    escalation = find_escalation(intake, [], PROCEDURE_TEXT)

    assert escalation is not None and escalation["classification"] == "ambiguous"
    assert "I did not authorize this charge." in [c["quote"] for c in escalation["citations"]]


def test_one_sentence_that_both_denies_and_confirms_is_ambiguous():
    intake = (
        "Source ID: TEST-INTAKE\n\n"
        "I did not authorize it, but I made this purchase with my wife's card.\n"
        "Authorization: not supplied\n"
    )

    escalation = find_escalation(intake, [], PROCEDURE_TEXT)

    assert escalation is not None and escalation["classification"] == "ambiguous"
    assert [c["claim"] for c in escalation["citations"]][:2] == [
        "authorization_denied",
        "authorization_confirmed",
    ]


def test_a_follow_up_that_reveals_a_cash_withdrawal_escalates():
    followup = (
        "# Customer follow-up email\n\nSource ID: TEST-FOLLOWUP\n\n"
        "Actually it was an ATM withdrawal and the machine paid out nothing.\n"
    )

    escalation = find_escalation(
        _intake("I do not recognize this charge.", authorization="denied"), [followup], PROCEDURE_TEXT
    )

    assert escalation is not None and escalation["classification"] == "unsupported"
    assert escalation["citations"][0]["source_id"] == "TEST-FOLLOWUP"


@pytest.mark.parametrize(
    "followup_text",
    [
        "Please withdraw my complaint. I found the receipt in my email.",
        "I no longer want to dispute this charge; my partner made it.",
        "Please cancel this dispute, the shop has sorted it out.",
        "I would like to withdraw my complaint.",
        "I would really like to withdraw my complaint.",
        "Could you please withdraw my complaint?",
        "Please withdraw my complaint if possible.",
        "I am not sure, but please withdraw my complaint.",
        "I may have been wrong, so please withdraw my complaint.",
        "Would you cancel my dispute, please?",
        "I'd like to drop my claim.",
        "Please withdraw my complaint; if you need anything else, call me.",
    ],
)
def test_a_follow_up_that_withdraws_the_complaint_is_ambiguous(followup_text):
    followup = f"# Customer follow-up email\n\nSource ID: TEST-FOLLOWUP\n\n{followup_text}\n"

    escalation = find_escalation(
        _intake("I do not recognize this charge.", authorization="denied"), [followup], PROCEDURE_TEXT
    )

    assert escalation is not None and escalation["classification"] == "ambiguous"
    assert escalation["reason"].startswith("The customer withdrew the complaint in TEST-FOLLOWUP.")
    withdrawn = [c for c in escalation["citations"] if c["claim"] == "complaint_withdrawn"]
    assert [c["source_id"] for c in withdrawn] == ["TEST-FOLLOWUP"]
    assert withdrawn[0]["quote"] in followup
    assert escalation["citations"][-1]["claim"] == "ambiguous_rule"


@pytest.mark.parametrize(
    "followup_text",
    [
        "I may withdraw my complaint if the shop refunds me.",
        "I could cancel my dispute if needed.",
        "If the shop refunds me, I will withdraw my complaint.",
        "I would withdraw my complaint, but the shop still has not refunded me.",
        "Please do not withdraw my complaint.",
        "I do not want to withdraw my complaint.",
        "I won't drop my claim.",
    ],
)
def test_a_hypothetical_or_negated_withdrawal_has_not_withdrawn_anything(followup_text):
    """Kanit's #91 review: a conditional is not a withdrawal yet, and nor is a refusal."""
    followup = f"# Customer follow-up email\n\nSource ID: TEST-FOLLOWUP\n\n{followup_text}\n"

    escalation = find_escalation(
        _intake("I do not recognize this charge.", authorization="denied"), [followup], PROCEDURE_TEXT
    )

    assert escalation is None


def test_a_withdrawn_complaint_goes_to_a_person_without_a_deadline():
    followup = "# Customer follow-up email\n\nSource ID: TEST-FOLLOWUP\n\nPlease withdraw my complaint.\n"

    result = _assemble(_record(), statement="I do not recognize this charge.", customer_texts=[followup])

    assert (result["classification"], result["routing"], result["deadline"]) == (
        "ambiguous",
        "manual_review",
        None,
    )
    assert "Please withdraw my complaint." in [c["quote"] for c in result["citations"]]


def test_cancelling_something_other_than_the_complaint_is_not_a_withdrawal():
    followup = (
        "# Customer follow-up email\n\nSource ID: TEST-FOLLOWUP\n\n"
        "I also want to cancel my subscription.\n"
    )

    escalation = find_escalation(
        _intake("I do not recognize this charge.", authorization="denied"), [followup], PROCEDURE_TEXT
    )

    assert escalation is None


def test_a_withdrawal_is_read_only_from_a_later_statement():
    intake = _intake(
        "I may withdraw my complaint if the shop refunds me. I do not recognize it.",
        authorization="denied",
    )

    assert find_escalation(intake, [], PROCEDURE_TEXT) is None


@pytest.mark.parametrize(
    ("statement", "classification"),
    [
        (
            (
                "I didn't recognize the store at first, but I now remember buying from Tide Shop. "
                "The order never arrived."
            ),
            "service_not_received",
        ),
        (
            (
                "I thought I didn't recognize this payment, but it turns out it was my order, "
                "which never arrived."
            ),
            "service_not_received",
        ),
        (
            (
                "I didn't recognise Nova Tech until I checked my email. I did buy the headphones, "
                "but they were never delivered."
            ),
            "service_not_received",
        ),
        (
            "I didn't recognize the charge, but it was my order after all, and it never arrived.",
            "service_not_received",
        ),
        (
            "I didn't recognize it at first, but it was mine. It was charged twice.",
            "duplicate_charge",
        ),
        (
            (
                "At first I didn't recognize the charge, but now I remember it was my gym. "
                "Fern Gym charged me twice."
            ),
            "duplicate_charge",
        ),
    ],
)
def test_a_denial_of_recognition_the_customer_takes_back_does_not_conflict(
    statement, classification
):
    result = _assemble(_record(authorization="confirmed"), statement, authorization="confirmed")

    assert result["classification"] == classification


@pytest.mark.parametrize(
    "statement",
    [
        "I do not recognize this charge, and I still don't after checking my receipts.",
        "I didn't recognize the merchant name at first, and I still don't think I made it.",
        "I did not authorize it, but it turns out my son used my card.",
        # Kanit's #91 review: none of these recognises the purchase, so the denial stands.
        "I didn't recognize this charge, but it turns out it was charged twice.",
        "I didn't recognize this charge. I did buy a coffee there last week, but this one is not mine.",
        "I didn't recognize the charge, but I now remember I already called you about it.",
        # Recognition without a problem to dispute instead does not take the denial back.
        "I didn't recognize the charge, but it turns out it was my order.",
        "I didn't recognize this charge; it turns out it was my card number that was stolen.",
        (
            "I didn't recognize this charge; it turns out it was my card number that was stolen. "
            "The order never arrived."
        ),
        "I didn't recognize the charge, but it turns out it was my son.",
        "I don't recognize this charge; after all, I have never shopped there.",
        "I don't recognize this charge. After all, I was abroad that week.",
        "I don't recognize this charge after all my checks.",
        "I didn't recognize this charge, and none of it was mine.",
        "I do not recognize the charge. I did pay for my groceries in cash that day.",
        "I do not recognise this purchase. I did buy from that shop once, years ago.",
        # A problem without recognition, or recognition the customer contradicts.
        "I don't recognize this charge. The parcel I ordered elsewhere never arrived either.",
        "I didn't recognize it, then I remembered buying there in May, but this charge is not mine.",
    ],
)
def test_a_denial_that_is_not_taken_back_still_conflicts_with_a_confirmed_form(statement):
    result = _assemble(_record(authorization="confirmed"), statement, authorization="confirmed")

    assert (result["classification"], result["routing"]) == ("ambiguous", "manual_review")
    denied = [c for c in result["citations"] if c["claim"] == "authorization_denied"]
    assert denied and denied[0]["quote"] in statement


@pytest.mark.parametrize(
    "statement",
    [
        "Rio Gym charged me twice and the classes were never delivered.",
        "The shop charged me twice for one order. The order never arrived either.",
    ],
)
def test_a_complaint_with_a_duplicate_and_an_undelivered_service_goes_to_a_person(statement):
    # Before, the service check ran first and the case was drafted ready as a service
    # complaint (EDG-E18). The procedure gives each problem its own type, so neither wins.
    result = _assemble(_record(authorization="confirmed"), statement, authorization="confirmed")

    assert (result["classification"], result["routing"], result["deadline"]) == (
        "ambiguous",
        "manual_review",
        None,
    )
    competing = [c for c in result["citations"] if c["claim"] == "competing_classification"]
    assert [c["quote"] for c in competing] == [
        (
            "Use duplicate_charge for a report of two charges for one purchase; retrieve both "
            "transaction records."
        ),
        (
            "Use service_not_received for an authorized purchase whose promised service was "
            "not supplied."
        ),
    ]
    assert all(c["quote"] in PROCEDURE_TEXT for c in competing)
    assert "reports both a duplicate charge and a service" in result["narrative"]


def test_two_problems_on_a_denied_form_are_still_unauthorized():
    statement = "Rio Gym charged me twice and the classes were never delivered."

    result = _assemble(_record(authorization="denied"), statement, authorization="denied")

    assert result["classification"] == "unauthorized"


@pytest.mark.parametrize(
    "statement",
    [
        "This is not a double charge. The classes were never delivered.",
        # HLD-H02: "isn't" denies the duplicate as "is not" does.
        "It isn't a double charge. The yoga classes I paid for were never delivered.",
    ],
)
def test_a_denied_duplicate_beside_an_undelivered_service_is_one_problem(statement):
    result = _assemble(_record(authorization="confirmed"), statement, authorization="confirmed")

    assert result["classification"] == "service_not_received"


def test_without_problems_to_name_a_denial_of_recognition_is_never_taken_back():
    statement = (
        "I didn't recognize the store at first, but I now remember buying from Tide Shop. "
        "The order never arrived."
    )

    escalation = find_escalation(_intake(statement, authorization="confirmed"), [], PROCEDURE_TEXT)

    assert escalation is not None and escalation["classification"] == "ambiguous"


def test_a_taken_back_denial_with_an_undelivered_order_is_drafted_as_service():
    record = _record(authorization="confirmed")

    result = _assemble(
        record,
        statement=(
            "I didn't recognize the store at first, but I now remember buying from Tide Shop. "
            "The problem is the order never arrived."
        ),
        authorization="confirmed",
    )

    assert (result["classification"], result["routing"]) == ("service_not_received", "ready_for_review")


def test_an_escalated_case_with_no_single_amount_line_is_still_drafted():
    attachment = "# Purchase supporting material\n\nSource ID: TEST-ATTACHMENT\n"

    result = _assemble(_record(), statement="My ATM withdrawal failed.", attachment_text=attachment)

    assert result["classification"] == "unsupported" and result["routing"] == "manual_review"
    assert {"claim": "customer_evidence", "source_id": "TEST-ATTACHMENT", "quote": "Source ID: TEST-ATTACHMENT"} in (
        result["citations"]
    )


def test_an_unsupported_case_requests_no_field_even_when_the_form_is_blank():
    """A cash withdrawal has no required field, so blank form lines are not questioned."""
    record = _record(
        authorization="not supplied",
        missing=["authorization_confirmation", "promised_service_date", "purchase_receipt"],
    )

    result = _assemble(
        record, statement="I took cash out at an ATM and none came out.", authorization="not supplied"
    )

    assert (result["classification"], result["routing"]) == ("unsupported", "manual_review")
    assert result["missing_information"] == []
    assert result["follow_up_questions"] == []
    assert not any(c["quote"].startswith("Manual review takes precedence") for c in result["citations"])
    assert "Missing information" not in result["narrative"]


def test_an_ambiguous_case_does_not_request_a_field_another_type_needs():
    followup = "# Customer follow-up email\n\nSource ID: TEST-FOLLOWUP\n\nAuthorization: confirmed\n"

    result = _assemble(
        _record(missing=["promised_service_date", "purchase_receipt"]),
        statement="Please look at this charge.",
        customer_texts=[followup],
    )

    assert result["classification"] == "ambiguous"
    assert result["missing_information"] == []
    assert result["follow_up_questions"] == []


def test_a_missing_field_without_a_question_is_a_contract_error():
    record = _record(missing=["receipt_photo"])

    with pytest.raises(ContractError, match="unknown missing information identifier"):
        _assemble(record, statement="My ATM withdrawal failed.")


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
    attachment_text="Source ID: TEST-ATTACHMENT\nAmount: 90 XCR\n",
):
    record["intake"]["statement"] = statement
    return assemble_contract(
        record,
        intake_text=_intake(statement, authorization),
        attachment_text=attachment_text,
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
    # build_records lists a field as missing only when its intake line is absent, so a
    # listed form field is blank here too.
    missing = [] if missing is None else missing
    return {
        "case_id": "TEST-CASE",
        "intake": {
            "source_id": "TEST-INTAKE",
            "statement": "",
            "reported_date": "2026-10-01",
            "transaction_id": "TX-TEST",
            "authorization": authorization,
            "promised_service_date": (
                "not supplied" if "promised_service_date" in missing else "2026-08-20"
            ),
            "purchase_receipt": "not supplied" if "purchase_receipt" in missing else "attached",
            "submission_reference": "dispute-test",
        },
        "policy": {"version_id": "CARD-POLICY-V2", "procedure_id": "CARD-PROCEDURE-01"},
        "missing_information": missing,
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
