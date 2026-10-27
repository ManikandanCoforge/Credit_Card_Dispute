"""The escalation metric scores routing and classification against gold.

Every case yields exactly two verdicts: one for routing and one for
classification. An unbuilt case fails both and carries the build error, so a
stop is never scored as a wrong answer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from evals.contract import Check
from evals.metrics import escalation
from tests.evals.support import CONTRACT, GOLD, make_case, make_run

ROUTE = "escalation.route_correct"
CLASS = "escalation.class_correct"


def _checks(
    gold: Mapping[str, Any] | None = None,
    contract: Mapping[str, Any] | None = None,
    build_error: str | None = None,
) -> dict[str, Check]:
    """Return the checks for one case, keyed by metric name."""
    case = make_case(gold=gold, contract=contract, build_error=build_error)
    return {check.metric: check for check in escalation.run(make_run([case]))}


def _metrics(case_count: int) -> Sequence[str]:
    """Return the metric names emitted for a run of identical cases."""
    cases = [make_case(f"CASE-{index}") for index in range(case_count)]
    return [check.metric for check in escalation.run(make_run(cases))]


def test_ready_for_review_case_passes_both():
    checks = _checks()
    assert escalation.NAME == "escalation"
    assert set(checks) == {ROUTE, CLASS}
    assert all(check.passed for check in checks.values())
    assert set(checks[ROUTE].evidence) == {"got", "expected"}
    assert checks[ROUTE].evidence["got"] == "ready_for_review"
    assert checks[ROUTE].evidence["expected"] == ["ready_for_review"]
    assert checks[CLASS].evidence["got"] == "unauthorized"


def test_gold_manual_review_case_passes_when_contract_escalates():
    gold = {**GOLD, "routing": ["manual_review"]}
    contract = {**CONTRACT, "routing": "manual_review"}
    checks = _checks(gold=gold, contract=contract)
    assert all(check.passed for check in checks.values()), checks


def test_gold_with_several_allowed_values_accepts_any_of_them():
    gold = {**GOLD, "routing": ["ready_for_review", "manual_review"]}
    checks = _checks(gold=gold, contract={**CONTRACT, "routing": "manual_review"})
    assert checks[ROUTE].passed
    assert checks[ROUTE].evidence["expected"] == ["ready_for_review", "manual_review"]


def test_normal_case_routed_to_manual_review_is_a_false_escalation():
    contract = {**CONTRACT, "routing": "manual_review"}
    checks = _checks(contract=contract)
    route = checks[ROUTE]
    assert not route.passed
    assert checks[CLASS].passed
    assert route.evidence["got"] == "manual_review"
    assert route.evidence["expected"] == ["ready_for_review"]
    assert "manual_review" in route.reason


def test_wrong_classification_fails_class_correct_while_route_passes():
    contract = {**CONTRACT, "classification": "duplicate_charge"}
    checks = _checks(contract=contract)
    assert checks[ROUTE].passed
    assert not checks[CLASS].passed
    assert checks[CLASS].evidence["got"] == "duplicate_charge"
    assert checks[CLASS].evidence["expected"] == ["unauthorized"]


def test_unbuilt_case_fails_both_with_the_build_error():
    checks = _checks(build_error="ContractError: no policy establishes a deadline")
    assert set(checks) == {ROUTE, CLASS}
    for check in checks.values():
        assert not check.passed
        assert "ContractError: no policy establishes a deadline" in check.reason
        assert check.evidence["got"] is None
        assert (
            check.evidence["error"] == "ContractError: no policy establishes a deadline"
        )
    assert checks[ROUTE].evidence["expected"] == ["ready_for_review"]


@pytest.mark.parametrize("case_count", [1, 2, 7])
def test_every_case_emits_exactly_two_checks(case_count):
    metrics = _metrics(case_count)
    assert len(metrics) == case_count * 2
    assert set(metrics) == {ROUTE, CLASS}


def test_a_contract_without_the_field_fails_only_that_check():
    contract = {key: value for key, value in CONTRACT.items() if key != "routing"}
    checks = _checks(contract=contract)
    assert not checks[ROUTE].passed
    assert checks[ROUTE].evidence["got"] is None
    assert checks[CLASS].passed


def test_gold_without_allowed_values_never_passes():
    checks = _checks(gold={**GOLD, "routing": [], "classification": ["unauthorized"]})
    assert not checks[ROUTE].passed
    assert checks[ROUTE].evidence["expected"] == []
    assert checks[ROUTE].evidence["got"] == "ready_for_review"
