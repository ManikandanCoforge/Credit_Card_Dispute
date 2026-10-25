"""The draft narrative for a normal case, on the template path and the model path.

Expected values come from docs/OUTPUT_CONTRACT.md ("covering evidence,
recommendation, uncertainty and limitations"; "Mark customer communications as
drafts") and CARD-PROCEDURE-01 ("No promise of refund, success, reimbursement,
or eligibility").
"""

import json
import re
from pathlib import Path

import pytest

from src.build_records import build_complaint_records
from src.contract import assemble_contract, assemble_draft
from src.narrative import (
    REPLY_MARKER,
    SECTIONS,
    draft_narrative,
    narrative_problems,
    template_narrative,
)

DEV = Path(__file__).resolve().parents[1] / "data" / "dev"
PROMISES = re.compile(r"refund|reimburs|guarantee|eligib|approved|success", re.IGNORECASE)


def test_card_d01_narrative_has_the_four_sections_in_order_then_a_draft_reply():
    narrative = assemble_contract(**_d01_arguments())["narrative"]

    positions = [narrative.index(marker) for marker in (*SECTIONS, REPLY_MARKER)]
    assert positions == sorted(positions)
    assert narrative.startswith("Draft for human review.")
    assert "Customer reply (DRAFT, not sent):" in narrative
    assert "The transaction service shows 117 XCR." in narrative
    assert "The policy deadline is 2026-10-31." in narrative


def test_card_d01_narrative_makes_no_promise_and_carries_no_restricted_value():
    narrative = assemble_contract(**_d01_arguments())["narrative"]

    assert PROMISES.search(narrative) is None
    assert "CUST-D01" not in narrative
    assert "SYNTHETIC-PRIVATE" not in narrative
    assert narrative_problems(narrative, narrative) == []


def test_the_template_path_uses_no_model_and_is_measured():
    contract, meter = assemble_draft(**_d01_arguments())

    assert meter["narrative_path"] == "template"
    assert meter["model_calls"] == 0
    assert meter["narrative_latency_ms"] >= 0
    assert contract == assemble_contract(**_d01_arguments())


def test_a_model_changes_the_prose_only_and_every_rule_field_is_byte_identical():
    template, _meter = assemble_draft(**_d01_arguments())
    reworded = template["narrative"].replace(
        "A reviewer can check the cited evidence and decide.",
        "The reviewer should check the cited evidence before deciding.",
    )

    contract, meter = assemble_draft(**_d01_arguments(), writer=lambda _draft: reworded)

    assert meter["narrative_path"] == "model"
    assert meter["model_calls"] == 1
    assert contract["narrative"] == reworded
    assert _rule_fields(contract) == _rule_fields(template)


def test_the_model_receives_only_the_template_draft():
    received = []

    def writer(draft):
        received.append(draft)
        return draft

    template, _meter = assemble_draft(**_d01_arguments())
    assemble_draft(**_d01_arguments(), writer=writer)

    assert received == [template["narrative"]]


@pytest.mark.parametrize(
    "rewrite",
    [
        lambda draft: draft + " We will refund you in full.",
        lambda draft: draft.replace("Limitations:", "Notes:"),
        lambda draft: draft.replace("Evidence:", "Background:"),
        lambda draft: draft + " Your reference is CUST-D01.",
        lambda draft: draft.replace("2026-10-31", "2026-11-30"),
        lambda draft: draft + " The charge was 118 XCR.",
    ],
)
def test_a_model_draft_that_breaks_a_rule_falls_back_to_the_template(rewrite):
    template, _meter = assemble_draft(**_d01_arguments())

    contract, meter = assemble_draft(
        **_d01_arguments(), writer=lambda draft: rewrite(draft)
    )

    assert meter["narrative_path"] == "template_fallback"
    assert meter["model_calls"] == 1
    assert contract == template


@pytest.mark.parametrize("failure", [OSError, ValueError, RuntimeError])
def test_a_model_that_fails_falls_back_to_the_template(failure):
    def writer(_draft):
        raise failure("unavailable")

    template, _meter = assemble_draft(**_d01_arguments())
    contract, meter = assemble_draft(**_d01_arguments(), writer=writer)

    assert meter["narrative_path"] == "template_fallback"
    assert contract == template


def test_latency_is_measured_with_the_supplied_clock_on_both_paths():
    contract = assemble_contract(**_d01_arguments())
    ticks = iter([10.0, 10.25])
    _text, template_meter = draft_narrative(contract, clock=lambda: next(ticks))
    ticks = iter([20.0, 21.5])
    _text, model_meter = draft_narrative(
        contract, writer=lambda draft: draft, clock=lambda: next(ticks)
    )

    assert template_meter == {
        "narrative_path": "template",
        "narrative_latency_ms": 250.0,
        "model_calls": 0,
    }
    assert model_meter == {
        "narrative_path": "model",
        "narrative_latency_ms": 1500.0,
        "model_calls": 1,
    }


def test_missing_facts_questions_and_notes_are_stated_not_hidden():
    contract = {
        **assemble_contract(**_d01_arguments()),
        "routing": "request_information",
        "deadline": None,
        "facts": {
            "transaction_id": None,
            "amount": None,
            "currency": None,
            "reported_date": "2026-10-01",
        },
        "missing_information": ["purchase_receipt"],
        "follow_up_questions": [
            {"field": "purchase_receipt", "question": "Can you send the receipt?"}
        ],
    }

    narrative = template_narrative(contract, ["The merchant record could not be read."])

    assert "reports transaction not named" in narrative
    assert "amount and currency are left empty" in narrative
    assert (
        "Uncertainty: The merchant record could not be read. Missing information is still "
        "requested: purchase_receipt."
    ) in narrative
    assert "No deadline is set" in narrative
    assert "Ask the customer the follow-up questions before review." in narrative
    assert "To continue, please answer: Can you send the receipt?" in narrative


def _rule_fields(contract):
    return json.dumps({key: value for key, value in contract.items() if key != "narrative"})


def _d01_arguments():
    record = build_complaint_records(
        [{"case_id": "CARD-D01", "intake_source": "CARD-D01-INTAKE"}], DEV
    )[0]
    body = {
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
    }
    record["transactions"] = body["transactions"]
    return {
        "record": record,
        "intake_text": (DEV / "documents" / "CARD-D01-INTAKE.md").read_text(encoding="utf-8"),
        "attachment_text": (DEV / "documents" / "CARD-D01-ATTACHMENT.md").read_text(
            encoding="utf-8"
        ),
        "procedure_text": (DEV / "policies" / "CARD-PROCEDURE-01.md").read_text(encoding="utf-8"),
        "policy_text": (DEV / "policies" / "CARD-POLICY-V2.md").read_text(encoding="utf-8"),
        "transactions_text": json.dumps(body, sort_keys=True),
    }
