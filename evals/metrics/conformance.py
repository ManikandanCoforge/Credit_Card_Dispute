"""Contract conformance: the supplied evaluator used as an oracle.

Owned by the conformance metric. The module turns `tools.evaluate.evaluate`
into one check per case per bank sub-check, so a failure names its field
instead of collapsing into `passed: false`.

A case that produced no contract short-circuits to a single
`conformance.submitted` check, because the evaluator reports exactly that and
the field checks would bury the build error. The same key carries a case
the gold file does not mention: the evaluator then returns no result for it,
and an unscored case must not read as a pass.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from evals.contract import CaseOutcome, Check, RunData
from tools.evaluate import evaluate

NAME = "conformance"

SUBMITTED = "submitted"
"""The sub-check the evaluator reports when a case was never built."""


def _scores(run: RunData) -> dict[str, Mapping[str, Any]]:
    """Return the supplied evaluator's per-case report, keyed by case id."""
    report = evaluate(run.dataset, run.gold, run.submissions())
    return {str(result["case_id"]): result for result in report["cases"]}


def _reason(case: CaseOutcome, subcheck: str, passed: bool) -> str:
    """Return a reason naming the case, the sub-check and any build error."""
    verdict = "passes" if passed else "fails"
    reason = f"{case.case_id} {verdict} the supplied evaluator sub-check {subcheck}"
    if case.build_error:
        reason = f"{reason}; build error: {case.build_error}"
    return reason


def _unscored(case: CaseOutcome, reason: str) -> Check:
    """Return the single not-passed check for a case the evaluator never saw."""
    return Check(
        metric=f"{NAME}.{SUBMITTED}",
        case_id=case.case_id,
        passed=False,
        reason=reason,
        evidence={
            "subcheck": SUBMITTED,
            "value": False,
            "build_error": case.build_error,
        },
    )


def _case_checks(case: CaseOutcome, score: Mapping[str, Any] | None) -> list[Check]:
    """Return one check per sub-check the evaluator reported for one case."""
    if score is None:
        return [
            _unscored(
                case,
                f"{case.case_id} has no gold entry, "
                "so the supplied evaluator did not score it",
            )
        ]
    return [
        Check(
            metric=f"{NAME}.{name}",
            case_id=case.case_id,
            passed=bool(value),
            reason=_reason(case, name, bool(value)),
            evidence={
                "subcheck": name,
                "value": bool(value),
                "build_error": case.build_error,
            },
        )
        for name, value in score.get("checks", {}).items()
    ]


def run(run: RunData) -> list[Check]:
    """Return one check per case per supplied-evaluator sub-check."""
    scores = _scores(run)
    return [
        check
        for case in run.cases
        for check in _case_checks(case, scores.get(case.case_id))
    ]
