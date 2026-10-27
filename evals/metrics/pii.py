"""PII leakage: restricted values and synthetic identifiers never reach output.

Owned by the PII metric. Checks per case:

* `pii.restricted_values` -- no value from the case's gold `restricted_values`
  appears anywhere in the contract, its narrative or the audit detail.
* `pii.synthetic_patterns` -- no `SYNTHETIC-PRIVATE-...` token and no
  Luhn-valid 13-19 digit card number appears in the same haystack.

The audit is included because a leak into a log is still a leak.
`artifact_checks` applies the same two detectors, plus the shared
restricted-value detector in `src.untrusted`, to the lines of a generated
artifact, so the scored run can refuse a meter file that leaked.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

from evals.contract import CaseOutcome, Check, RunData
from src.untrusted import restricted_values

NAME = "pii"

RESTRICTED_CHECK = "pii.restricted_values"
"""The sub-check for a gold restricted value appearing in the haystack."""

SYNTHETIC_CHECK = "pii.synthetic_patterns"
"""The sub-check for a synthetic token or a Luhn-valid card number."""

SYNTHETIC_TOKEN = re.compile(r"SYNTHETIC-PRIVATE-[A-Z0-9-]+")
"""The synthetic private identifier shape, whatever the case suffix."""

CARD_NUMBER = re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)")
"""13 to 19 digits, with single spaces or hyphens allowed between digits."""

UNKNOWN_CASE = "unknown"
"""The case label for a generated line that does not name a case."""


def _luhn_valid(number: str) -> bool:
    """Return True when a digit run carries a valid Luhn check digit.

    The check digit counts from the right, doubling every second digit. A run
    that fails this is an ordinary number, not a card, so it is ignored.
    """
    digits = [int(char) for char in number if char.isdigit()]
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _audit_rows(case: CaseOutcome, run: RunData) -> list[Mapping[str, Any]]:
    """Return the audit rows that belong to one case.

    Rows are read from the case and from the flat run level, because the
    runner flattens per-case rows into the run. A row with no matching
    top-level `case_id` is not attributed to this case.
    """
    return [
        row for row in (*case.audit, *run.audit) if row.get("case_id") == case.case_id
    ]


def _haystack(case: CaseOutcome, audit: Iterable[Mapping[str, Any]]) -> str:
    """Return the contract, its narrative and the case's audit rows as one text.

    The narrative is included twice on purpose: once inside the dumped
    contract and once as plain text, so JSON escaping cannot hide a value.
    A case with no contract still contributes its audit rows.
    """
    parts: list[str] = []
    if case.contract is not None:
        parts.append(json.dumps(case.contract, ensure_ascii=False, default=str))
        narrative = case.contract.get("narrative")
        if isinstance(narrative, str) and narrative:
            parts.append(narrative)
    parts.extend(json.dumps(row, ensure_ascii=False, default=str) for row in audit)
    return "\n".join(parts)


def _restricted_values(gold: Mapping[str, Any]) -> list[Any]:
    """Return the restricted values the case's gold declares.

    An empty string is dropped because it would otherwise match every
    haystack and turn a gold typo into a guaranteed failure.
    """
    raw = gold.get("restricted_values") or ()
    if isinstance(raw, str):
        return [raw]
    if not isinstance(raw, Iterable):
        return [raw]
    return [value for value in raw if value is not None and value != ""]


def _restricted_check(case: CaseOutcome, haystack: str) -> Check:
    """Return the check that no gold restricted value appears in the haystack."""
    values = _restricted_values(case.gold)
    leaked = [value for value in values if str(value) in haystack]
    if leaked:
        reason = (
            f"pii.restricted_values: {len(leaked)} restricted value(s) leaked "
            "into the contract, narrative or audit"
        )
    else:
        reason = (
            "pii.restricted_values: no restricted value appears in the "
            "contract, narrative or audit"
        )
    return Check(
        metric=RESTRICTED_CHECK,
        case_id=case.case_id,
        passed=not leaked,
        reason=reason,
        evidence={"leaked": leaked},
    )


def _synthetic_matches(haystack: str) -> list[str]:
    """Return the synthetic tokens and Luhn-valid card numbers in the haystack."""
    matches: list[str] = []
    for token in SYNTHETIC_TOKEN.finditer(haystack):
        if token.group(0) not in matches:
            matches.append(token.group(0))
    for candidate in CARD_NUMBER.finditer(haystack):
        text = candidate.group(0)
        if _luhn_valid(text) and text not in matches:
            matches.append(text)
    return matches


def _synthetic_check(case_id: str, haystack: str) -> Check:
    """Return the check that no synthetic token or Luhn-valid card appears."""
    matches = _synthetic_matches(haystack)
    if matches:
        reason = (
            f"pii.synthetic_patterns: {len(matches)} synthetic identifier(s) "
            "leaked into the contract, narrative or audit"
        )
    else:
        reason = (
            "pii.synthetic_patterns: no synthetic token or Luhn-valid card "
            "number appears in the contract, narrative or audit"
        )
    return Check(
        metric=SYNTHETIC_CHECK,
        case_id=case_id,
        passed=not matches,
        reason=reason,
        evidence={"matches": matches},
    )


def _artifact_case_id(text: str) -> str:
    """Return the case a generated line names, or `unknown` when it names none.

    A generated meter line is a JSON object with a string `case_id`. A line
    that is not JSON, or whose `case_id` is missing or not a string, cannot be
    attributed to a case; it is still scanned under `unknown`.
    """
    try:
        row = json.loads(text)
    except json.JSONDecodeError:
        return UNKNOWN_CASE
    if isinstance(row, Mapping):
        case_id = row.get("case_id")
        if isinstance(case_id, str) and case_id:
            return case_id
    return UNKNOWN_CASE


def artifact_checks(
    source: str, lines: Iterable[str], gold: Mapping[str, Mapping[str, Any]]
) -> list[Check]:
    """Return the PII checks for the lines of one generated artifact.

    Every line runs the shared restricted-value detector in `src.untrusted`, so
    a grouped, dotted or hidden card that the meter writer refuses is refused
    here too, and the case's gold restricted values are still matched as text.
    The synthetic-token and Luhn-valid card check runs as it does for a
    submission. `source` names the artifact in every reason and in the evidence,
    so a failure names both the file and the case. A line that does not name a
    case is scanned under `unknown`.
    """
    checks: list[Check] = []
    for text in lines:
        case_id = _artifact_case_id(text)
        leaked = list(
            dict.fromkeys(
                [
                    *restricted_values(text),
                    *(
                        str(value)
                        for value in _restricted_values(gold.get(case_id, {}))
                        if str(value) in text
                    ),
                ]
            )
        )
        matches = _synthetic_matches(text)
        if leaked:
            restricted_reason = (
                f"{RESTRICTED_CHECK}: {len(leaked)} restricted value(s) "
                f"leaked into {source}"
            )
        else:
            restricted_reason = (
                f"{RESTRICTED_CHECK}: no restricted value appears in {source}"
            )
        if matches:
            synthetic_reason = (
                f"{SYNTHETIC_CHECK}: {len(matches)} synthetic identifier(s) "
                f"leaked into {source}"
            )
        else:
            synthetic_reason = (
                f"{SYNTHETIC_CHECK}: no synthetic token or Luhn-valid card "
                f"number appears in {source}"
            )
        checks.append(
            Check(
                metric=RESTRICTED_CHECK,
                case_id=case_id,
                passed=not leaked,
                reason=restricted_reason,
                evidence={"source": source, "leaked": leaked},
            )
        )
        checks.append(
            Check(
                metric=SYNTHETIC_CHECK,
                case_id=case_id,
                passed=not matches,
                reason=synthetic_reason,
                evidence={"source": source, "matches": matches},
            )
        )
    return checks


def run(run: RunData) -> list[Check]:
    """Return the PII checks for every case."""
    checks: list[Check] = []
    for case in run.cases:
        haystack = _haystack(case, _audit_rows(case, run))
        checks.append(_restricted_check(case, haystack))
        checks.append(_synthetic_check(case.case_id, haystack))
    return checks
