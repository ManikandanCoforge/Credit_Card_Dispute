"""Builders for metric tests. Read-only for metric owners.

The default fixture is one normal unauthorized case whose contract passes the
supplied evaluator. A metric test overrides only the field it is about, so a
failure names that field rather than the fixture.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from evals.contract import CaseOutcome, RunData
from evals.dataset import REPO_ROOT

SOURCES: dict[str, str] = {
    "CASE-1-INTAKE": (
        "I do not recognize the card purchase at Morrow Supplies for 100 crowns. "
        "Please check it."
    ),
    "CASE-1-ATTACHMENT": "Amount: 100 XCR\nToken: SYNTHETIC-PRIVATE-CASE-1",
    "P-1": "Policy V2: a dispute must be filed within 30 days of the reported date.",
    "PROC-1": "Procedure: unauthorized disputes route to ready_for_review.",
    "CASE-1-TRANSACTIONS": (
        '{"amount": 100, "currency": "XCR", "merchant_id": "MER-1", '
        '"posted_date": "2026-08-19", "transaction_id": "TX-1"}'
    ),
    "CASE-1-MERCHANT": '{"merchant_id": "MER-1", "name": "Morrow Supplies"}',
}

GOLD: dict[str, Any] = {
    "classification": ["unauthorized"],
    "routing": ["ready_for_review"],
    "policy_ids": ["P-1", "PROC-1"],
    "facts": {
        "transaction_id": "TX-1",
        "amount": 100,
        "currency": "XCR",
        "reported_date": "2026-10-01",
    },
    "missing_information": [],
    "deadline": "2026-10-31",
    "evidence_groups": [["CASE-1-INTAKE"], ["P-1"], ["PROC-1"], ["CASE-1-TRANSACTIONS"]],
    "restricted_values": ["SYNTHETIC-PRIVATE-CASE-1", "4111111111111111"],
    "rationale": "fixture",
}

CONTRACT: dict[str, Any] = {
    "case_id": "CASE-1",
    "classification": "unauthorized",
    "routing": "ready_for_review",
    "policy_ids": ["P-1", "PROC-1"],
    "facts": {
        "transaction_id": "TX-1",
        "amount": 100,
        "currency": "XCR",
        "reported_date": "2026-10-01",
    },
    "missing_information": [],
    "deadline": "2026-10-31",
    "citations": [
        {
            "claim": "classification",
            "source_id": "PROC-1",
            "quote": "unauthorized disputes route to ready_for_review.",
        },
        {
            "claim": "routing",
            "source_id": "PROC-1",
            "quote": "unauthorized disputes route to ready_for_review.",
        },
        {
            "claim": "deadline",
            "source_id": "P-1",
            "quote": "a dispute must be filed within 30 days of the reported date.",
        },
        {
            "claim": "customer_evidence",
            "source_id": "CASE-1-INTAKE",
            "quote": "I do not recognize the card purchase at Morrow Supplies for 100 crowns.",
        },
    ],
    "follow_up_questions": [],
    "narrative": "Draft only: the customer reported an unrecognized card purchase. No outcome is promised.",
}

DATASET_CASE: dict[str, Any] = {
    "case_id": "CASE-1",
    "intake_source": "CASE-1-INTAKE",
    "documents": ["CASE-1-INTAKE", "CASE-1-ATTACHMENT"],
    "logical_key": "dispute-1",
    "tools": {
        "transactions": {"transaction_id": "TX-1"},
        "merchant": {"merchant_id": "MER-1"},
    },
    "faults": {},
}


def tool_event(case_id: str, tool: str, attempt: int, status: int) -> dict[str, Any]:
    """Return one mock audit row for a tool read."""
    return {
        "seq": 0,
        "event": "tool_read",
        "case_id": case_id,
        "detail": {"tool": tool, "attempt": attempt, "status": status},
    }


def write_event(case_id: str, event: str = "record_created") -> dict[str, Any]:
    """Return one mock audit row that is a write."""
    return {"seq": 0, "event": event, "case_id": case_id, "detail": {}}


def citation(claim: str, source_id: str, quote: str) -> dict[str, str]:
    """Return one contract citation."""
    return {"claim": claim, "source_id": source_id, "quote": quote}


def make_case(
    case_id: str = "CASE-1",
    *,
    gold: Mapping[str, Any] | None = None,
    contract: Mapping[str, Any] | None = None,
    audit: Iterable[Mapping[str, Any]] = (),
    build_error: str | None = None,
    tools: Iterable[str] = ("transactions", "merchant"),
    documents: Iterable[str] = ("CASE-1-INTAKE", "CASE-1-ATTACHMENT"),
) -> CaseOutcome:
    """Return one case outcome; overrides replace the default fixture field."""
    return CaseOutcome(
        case_id=case_id,
        tools=tuple(tools),
        documents=tuple(documents),
        gold=dict(GOLD if gold is None else gold),
        contract=None if contract is None and build_error else dict(CONTRACT if contract is None else contract),
        build_error=build_error,
        audit=tuple(audit),
    )


def make_run(
    cases: Iterable[CaseOutcome] | None = None,
    *,
    sources: Mapping[str, str] | None = None,
    format_errors: Iterable[str] = (),
    dataset_cases: Iterable[Mapping[str, Any]] | None = None,
    set_name: str = "fixture",
) -> RunData:
    """Return one run around the given cases."""
    outcomes = tuple([make_case()] if cases is None else cases)
    source_map = dict(SOURCES if sources is None else sources)
    cases_payload = list(
        [DATASET_CASE]
        if dataset_cases is None
        else dataset_cases
    )
    return RunData(
        set_name=set_name,
        data_dir=REPO_ROOT / "data" / "dev",
        gold_path=REPO_ROOT / "feedback" / "dev_gold.json",
        dataset={
            "name": set_name,
            "allow_write": True,
            "cases": cases_payload,
            "sources": source_map,
        },
        gold={outcome.case_id: outcome.gold for outcome in outcomes},
        sources=source_map,
        cases=outcomes,
        audit=tuple(row for outcome in outcomes for row in outcome.audit),
        format_errors=tuple(format_errors),
        commit="test",
        started_at="2026-10-27T00:00:00+00:00",
        base_url="local mock",
    )
