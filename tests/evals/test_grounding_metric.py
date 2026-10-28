"""The grounding metric must separate a broken quote from an uncited claim.

Every test overrides one fixture field, so a failure names the contract field it
is about rather than the fixture.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from evals.contract import CaseOutcome, Check
from evals.metrics import grounding
from tests.evals.support import CONTRACT, citation, make_case, make_run

CITATION_EXACT = "grounding.citation_exact"
CLAIM_SOURCES = "grounding.claim_sources"


def contract(**overrides: Any) -> dict[str, Any]:
    """Return a copy of the fixture contract with the named fields replaced."""
    payload = copy.deepcopy(CONTRACT)
    payload.update(overrides)
    return payload


def checks(outcome: CaseOutcome) -> dict[str, Check]:
    """Run the metric over one case and index the two checks it must emit."""
    result = grounding.run(make_run([outcome]))
    assert [check.metric for check in result] == [CITATION_EXACT, CLAIM_SOURCES]
    assert all(check.case_id == outcome.case_id for check in result)
    return {check.metric: check for check in result}


def test_clean_case_passes_both_checks() -> None:
    result = checks(make_case())
    assert result[CITATION_EXACT].passed
    assert result[CITATION_EXACT].evidence["invalid"] == []
    assert result[CLAIM_SOURCES].passed
    assert result[CLAIM_SOURCES].evidence["missing"] == []
    assert "routing" in result[CLAIM_SOURCES].evidence["claims"]


def test_quote_not_in_its_source_fails_only_citation_exact() -> None:
    citations = copy.deepcopy(CONTRACT["citations"])
    citations[1] = citation(
        "routing",
        "PROC-1",
        "an invented sentence that appears in no source.",
    )
    result = checks(make_case(contract=contract(citations=citations)))
    assert not result[CITATION_EXACT].passed
    assert result[CITATION_EXACT].evidence["invalid"][0]["claim"] == "routing"
    assert result[CITATION_EXACT].evidence["invalid"][0]["reason"]
    assert result[CLAIM_SOURCES].passed


def test_unknown_source_id_fails_citation_exact() -> None:
    citations = copy.deepcopy(CONTRACT["citations"])
    citations[3] = citation(
        "customer_evidence",
        "CASE-9-NOWHERE",
        "I do not recognize the card purchase at Morrow Supplies for 100 crowns.",
    )
    result = checks(make_case(contract=contract(citations=citations)))
    assert not result[CITATION_EXACT].passed
    invalid = result[CITATION_EXACT].evidence["invalid"]
    assert len(invalid) == 1
    assert invalid[0]["source_id"] == "CASE-9-NOWHERE"
    assert "source" in invalid[0]["reason"]
    assert result[CLAIM_SOURCES].passed


def test_empty_quote_and_non_mapping_citation_fail_citation_exact() -> None:
    citations = copy.deepcopy(CONTRACT["citations"])
    citations[0] = citation("classification", "PROC-1", "")
    citations[3] = "not a citation object"
    result = checks(make_case(contract=contract(citations=citations)))
    assert not result[CITATION_EXACT].passed
    reasons = [item["reason"] for item in result[CITATION_EXACT].evidence["invalid"]]
    assert len(reasons) == 2
    assert any("quote" in reason for reason in reasons)
    assert any("object" in reason for reason in reasons)
    # The routing claim object is malformed but present, so claim_sources alone passes.
    assert result[CLAIM_SOURCES].passed


def test_no_citations_fails_both_checks() -> None:
    result = checks(make_case(contract=contract(citations=[])))
    assert not result[CITATION_EXACT].passed
    assert "citation" in result[CITATION_EXACT].reason
    assert not result[CLAIM_SOURCES].passed
    assert result[CLAIM_SOURCES].evidence["missing"] == [
        "classification",
        "deadline",
        "routing",
    ]


def test_missing_routing_citation_fails_only_claim_sources() -> None:
    citations = [
        c for c in copy.deepcopy(CONTRACT["citations"]) if c["claim"] != "routing"
    ]
    result = checks(make_case(contract=contract(citations=citations)))
    assert result[CITATION_EXACT].passed
    assert not result[CLAIM_SOURCES].passed
    assert result[CLAIM_SOURCES].evidence["missing"] == ["routing"]
    assert "routing" not in result[CLAIM_SOURCES].evidence["claims"]


def test_manual_review_without_rule_citation_fails_claim_sources() -> None:
    payload = contract(
        classification="ambiguous",
        routing="manual_review",
        deadline=None,
        citations=[
            citation(
                "routing",
                "PROC-1",
                "unauthorized disputes route to ready_for_review.",
            )
        ],
    )
    result = checks(make_case(contract=payload))
    assert result[CITATION_EXACT].passed
    assert not result[CLAIM_SOURCES].passed
    assert result[CLAIM_SOURCES].evidence["missing"] == ["manual_review_rule"]


@pytest.mark.parametrize(
    "claim",
    [
        "ambiguous_rule",
        "unsupported_rule",
        "supported_classifications",
        "competing_classification",
    ],
)
def test_manual_review_rule_citation_satisfies_claim_sources(claim: str) -> None:
    payload = contract(
        classification="unsupported",
        routing="manual_review",
        deadline=None,
        citations=[
            citation("routing", "PROC-1", "unauthorized disputes route to"),
            citation(claim, "P-1", "a dispute must be filed within 30 days"),
        ],
    )
    result = checks(make_case(contract=payload))
    assert result[CITATION_EXACT].passed
    assert result[CLAIM_SOURCES].passed
    assert result[CLAIM_SOURCES].evidence["missing"] == []


def test_outage_citation_satisfies_the_manual_review_rule() -> None:
    """The procedure's stop-retrying sentence is a rule citation too."""
    payload = contract(
        classification="unsupported",
        routing="manual_review",
        deadline=None,
        citations=[
            citation("routing", "PROC-1", "unauthorized disputes route to"),
            citation(
                "transaction_service_unavailable",
                "PROC-1",
                "Procedure: unauthorized",
            ),
        ],
    )
    result = checks(make_case(contract=payload))
    assert result[CITATION_EXACT].passed
    assert result[CLAIM_SOURCES].passed
    assert result[CLAIM_SOURCES].evidence["missing"] == []


def test_unsupported_classification_needs_no_classification_citation() -> None:
    payload = contract(
        classification="unsupported",
        routing="ready_for_review",
        deadline=None,
        citations=[
            citation(
                "routing", "PROC-1", "unauthorized disputes route to ready_for_review."
            ),
        ],
    )
    result = checks(make_case(contract=payload))
    assert result[CITATION_EXACT].passed
    assert result[CLAIM_SOURCES].passed


def test_unbuilt_case_fails_both_checks_with_the_build_error() -> None:
    result = checks(make_case(build_error="assembly exploded on CASE-1"))
    assert not result[CITATION_EXACT].passed
    assert not result[CLAIM_SOURCES].passed
    assert (
        result[CITATION_EXACT].evidence["build_error"] == "assembly exploded on CASE-1"
    )
    assert (
        result[CLAIM_SOURCES].evidence["build_error"] == "assembly exploded on CASE-1"
    )


def test_null_contract_without_build_error_does_not_crash() -> None:
    outcome = CaseOutcome(
        case_id="CASE-1",
        tools=("transactions", "merchant"),
        documents=("CASE-1-INTAKE", "CASE-1-ATTACHMENT"),
        gold=make_case().gold,
        contract=None,
        build_error=None,
    )
    result = checks(outcome)
    assert not result[CITATION_EXACT].passed
    assert not result[CLAIM_SOURCES].passed
    assert result[CITATION_EXACT].evidence["build_error"] is None
    assert result[CLAIM_SOURCES].evidence["build_error"] is None


def test_two_cases_emit_two_checks_each_in_order() -> None:
    broken = make_case(contract=contract(citations=[]))
    clean = make_case(case_id="CASE-2")
    result = grounding.run(make_run([broken, clean]))
    assert [check.metric for check in result] == [
        CITATION_EXACT,
        CLAIM_SOURCES,
        CITATION_EXACT,
        CLAIM_SOURCES,
    ]
    assert [check.case_id for check in result] == [
        "CASE-1",
        "CASE-1",
        "CASE-2",
        "CASE-2",
    ]
    assert [check.passed for check in result] == [False, False, True, True]
