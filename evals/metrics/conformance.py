"""Contract conformance: the supplied evaluator used as an oracle.

Owned by the conformance metric. The module turns `tools.evaluate.evaluate`
into one check per case per bank sub-check, so a failure names its field
instead of collapsing into `passed: false`.

Every case gets every sub-check, even a case that produced no contract. A
not-built case fails `submitted` and the sub-checks the evaluator knows about,
so the denominator is the case count rather than the built count. That stops
eleven 100 percent rows from sitting beside three cases that produced nothing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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


def _subchecks(scores: Mapping[str, Mapping[str, Any]]) -> tuple[str, ...]:
    """Return every sub-check the evaluator reported, in first-seen order."""
    names: list[str] = []
    for score in scores.values():
        for name in score.get("checks", {}):
            if name != SUBMITTED and name not in names:
                names.append(name)
    return tuple(names)


def _reason(case: CaseOutcome, subcheck: str, passed: bool, reported: bool) -> str:
    """Return a reason naming the case, the sub-check and any build error."""
    if not reported:
        detail = case.build_error or "the case produced no contract"
        return f"{case.case_id} was not scored for {subcheck}: {detail}"
    verdict = "passes" if passed else "fails"
    reason = f"{case.case_id} {verdict} the supplied evaluator sub-check {subcheck}"
    if case.build_error:
        reason = f"{reason}; build error: {case.build_error}"
    return reason


def _submitted(case: CaseOutcome, score: Mapping[str, Any] | None) -> Check:
    """Return the check that says whether the evaluator received a contract."""
    reported = score.get("checks", {}) if score is not None else {}
    passed = bool(reported.get(SUBMITTED, score is not None))
    if score is None:
        reason = (
            f"{case.case_id} has no gold entry, "
            "so the supplied evaluator did not score it"
        )
    else:
        reason = _reason(case, SUBMITTED, passed, reported=SUBMITTED in reported)
    return Check(
        metric=f"{NAME}.{SUBMITTED}",
        case_id=case.case_id,
        passed=passed,
        reason=reason,
        evidence={
            "subcheck": SUBMITTED,
            "value": passed,
            "reported": SUBMITTED in reported,
            "build_error": case.build_error,
        },
    )


def _case_checks(
    case: CaseOutcome,
    score: Mapping[str, Any] | None,
    known: Sequence[str],
) -> list[Check]:
    """Return every sub-check for one case, scoring an unreported check as failed."""
    reported = score.get("checks", {}) if score is not None else {}
    checks = [_submitted(case, score)]
    for name in known:
        present = name in reported
        passed = bool(reported[name]) if present else False
        checks.append(
            Check(
                metric=f"{NAME}.{name}",
                case_id=case.case_id,
                passed=passed,
                reason=_reason(case, name, passed, reported=present),
                evidence={
                    "subcheck": name,
                    "value": passed,
                    "reported": present,
                    "build_error": case.build_error,
                },
            )
        )
    return checks


def run(run: RunData) -> list[Check]:
    """Return one check per case per supplied-evaluator sub-check."""
    scores = _scores(run)
    known = _subchecks(scores)
    return [
        check
        for case in run.cases
        for check in _case_checks(case, scores.get(case.case_id), known)
    ]
