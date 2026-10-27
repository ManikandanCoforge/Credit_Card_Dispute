"""Escalation accuracy: normal cases stay normal, escalated cases escalate.

Owned by the escalation metric. Checks per case:

* `escalation.route_correct` -- the routing is the one gold allows.
* `escalation.class_correct` -- the classification is the one gold allows.

The report derives normal-case accuracy, correct escalations, missed
escalations and false escalations from these checks; the metric itself emits
only the two per-case verdicts.

Gold holds the permitted values as a list, so a case whose correct answer is
genuinely ambiguous can accept either routing. A case that was never built is
not a wrong answer: it fails both checks and carries the build error, so the
report never counts a stopped case as a false escalation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from evals.contract import CaseOutcome, Check, RunData

NAME = "escalation"

ROUTE_CHECK = "escalation.route_correct"
"""The routing verdict for one case."""

CLASS_CHECK = "escalation.class_correct"
"""The classification verdict for one case."""


def run(run: RunData) -> list[Check]:
    """Return the escalation checks for every case, in case order."""
    return [check for case in run.cases for check in _case_checks(case)]


def _case_checks(case: CaseOutcome) -> list[Check]:
    """Return the routing and classification verdicts for one case."""
    allowed_routing = _allowed(case.gold, "routing")
    allowed_class = _allowed(case.gold, "classification")
    if case.contract is None:
        error = case.build_error or "case has no contract"
        return [
            _unbuilt(case, ROUTE_CHECK, "routing", allowed_routing, error),
            _unbuilt(case, CLASS_CHECK, "classification", allowed_class, error),
        ]
    return [
        _verdict(
            case, ROUTE_CHECK, "routing", case.contract.get("routing"), allowed_routing
        ),
        _verdict(
            case,
            CLASS_CHECK,
            "classification",
            case.contract.get("classification"),
            allowed_class,
        ),
    ]


def _allowed(gold: Mapping[str, Any], key: str) -> list[str]:
    """Return the permitted gold values for one contract field."""
    raw = gold.get(key)
    if not isinstance(raw, (list, tuple)):
        return []
    return [value for value in raw if isinstance(value, str)]


def _verdict(
    case: CaseOutcome,
    metric: str,
    field: str,
    got: Any,
    allowed: Sequence[str],
) -> Check:
    """Return one check comparing the contract field against its gold values."""
    if not allowed:
        return Check(
            metric=metric,
            case_id=case.case_id,
            passed=False,
            reason=f"gold has no {field} value to compare against",
            evidence={"got": got, "expected": []},
        )
    passed = got in allowed
    return Check(
        metric=metric,
        case_id=case.case_id,
        passed=passed,
        reason=(
            f"{field} {got!r} is allowed"
            if passed
            else f"{field} {got!r} is not one of {allowed!r}"
        ),
        evidence={"got": got, "expected": list(allowed)},
    )


def _unbuilt(
    case: CaseOutcome,
    metric: str,
    field: str,
    allowed: Sequence[str],
    error: str,
) -> Check:
    """Return a failing check for a case the application never built."""
    return Check(
        metric=metric,
        case_id=case.case_id,
        passed=False,
        reason=f"{field} not scored: {error}",
        evidence={"got": None, "expected": list(allowed), "error": error},
    )
