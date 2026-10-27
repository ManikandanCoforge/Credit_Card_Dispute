"""The conformance metric must pin every verdict to its sub-check, per case.

Fixture note: `tests.evals.support.CONTRACT` carries no citation for the gold
`CASE-1-TRANSACTIONS` evidence group, so the supplied evaluator already fails
`required_evidence` on it. `baseline_contract` adds that single citation, which
makes the baseline fully conforming; each failure test then changes exactly the
field it is about and asserts which sub-check moves.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from evals.contract import Check
from evals.metrics import conformance
from tests.evals.support import (
    CONTRACT,
    DATASET_CASE,
    citation,
    make_case,
    make_run,
)

SUB_CHECKS = (
    "classification",
    "routing",
    "policy_selection",
    "facts",
    "missing_information",
    "deadline",
    "citations_valid",
    "required_evidence",
    "narrative_present",
    "no_restricted_values",
    "targeted_questions",
)
"""Every sub-check `tools.evaluate.evaluate` reports for a built contract."""

TRANSACTION_QUOTE = '"transaction_id": "TX-1"'


def baseline_contract() -> dict[str, Any]:
    """Return the fixture contract plus the citation the evaluator requires."""
    contract = dict(CONTRACT)
    contract["citations"] = [
        *CONTRACT["citations"],
        citation("transaction_fact", "CASE-1-TRANSACTIONS", TRANSACTION_QUOTE),
    ]
    return contract


def failed_sub_checks(checks: list[Check], case_id: str = "CASE-1") -> set[str]:
    """Return the sub-check names that failed for one case."""
    prefix = f"{conformance.NAME}."
    return {
        check.metric.removeprefix(prefix)
        for check in checks
        if check.case_id == case_id and not check.passed
    }


def test_baseline_passes_every_sub_check() -> None:
    """The default fixture, once conforming, fails nothing at all."""
    assert conformance.NAME == "conformance"
    checks = conformance.run(make_run([make_case(contract=baseline_contract())]))
    assert [check.metric for check in checks] == [
        f"conformance.{name}" for name in SUB_CHECKS
    ]
    assert [check.case_id for check in checks] == ["CASE-1"] * len(SUB_CHECKS)
    assert failed_sub_checks(checks) == set()
    assert all(check.passed for check in checks)
    assert all(check.evidence["build_error"] is None for check in checks)


def test_wrong_deadline_fails_only_deadline() -> None:
    """A single wrong field moves a single sub-check."""
    contract = baseline_contract()
    contract["deadline"] = "2026-11-30"
    checks = conformance.run(make_run([make_case(contract=contract)]))
    assert failed_sub_checks(checks) == {"deadline"}
    failed = next(check for check in checks if check.metric == "conformance.deadline")
    assert failed.passed is False
    assert failed.evidence == {
        "subcheck": "deadline",
        "value": False,
        "build_error": None,
    }


def test_missing_citation_fails_citations_valid() -> None:
    """An empty citation list fails citations_valid; required_evidence reads it too."""
    contract = baseline_contract()
    contract["citations"] = []
    checks = conformance.run(make_run([make_case(contract=contract)]))
    assert "citations_valid" in failed_sub_checks(checks)
    assert failed_sub_checks(checks) == {"citations_valid", "required_evidence"}


def test_unbuilt_case_fails_submitted_with_the_build_error() -> None:
    """A case that produced no contract gets exactly one submitted check."""
    run = make_run([make_case(build_error="build failed: transactions tool timed out")])
    checks = conformance.run(run)
    assert len(checks) == 1
    check = checks[0]
    assert (check.metric, check.case_id, check.passed) == (
        "conformance.submitted",
        "CASE-1",
        False,
    )
    assert check.evidence == {
        "subcheck": "submitted",
        "value": False,
        "build_error": "build failed: transactions tool timed out",
    }
    assert "transactions tool timed out" in check.reason


def test_multi_case_run_keeps_verdicts_separate() -> None:
    """One bad case must not colour its neighbours."""
    good = make_case(contract=baseline_contract())
    bad = make_case(
        "CASE-2",
        contract={**baseline_contract(), "case_id": "CASE-2", "routing": "closed"},
    )
    dataset_cases = [
        DATASET_CASE,
        {**DATASET_CASE, "case_id": "CASE-2", "logical_key": "dispute-2"},
    ]
    checks = conformance.run(make_run([good, bad], dataset_cases=dataset_cases))
    assert len(checks) == 2 * len(SUB_CHECKS)
    assert {check.case_id for check in checks} == {"CASE-1", "CASE-2"}
    assert failed_sub_checks(checks, "CASE-1") == set()
    assert failed_sub_checks(checks, "CASE-2") == {"routing"}


def test_case_absent_from_gold_fails_submitted() -> None:
    """A case the evaluator never scored must not read as a pass."""
    run = make_run([make_case(contract=baseline_contract())])
    checks = conformance.run(replace(run, gold={}))
    assert [check.metric for check in checks] == ["conformance.submitted"]
    assert checks[0].passed is False
    assert "gold" in checks[0].reason
