"""Evidence grounding: every citation resolves, and every claim has a source.

Owned by the grounding metric. Deterministic checks only:

* `grounding.citation_exact` -- at least one citation, every quote a non-empty
  exact substring of the source it names, every source id known.
* `grounding.claim_sources` -- the routing claim is cited; a supported
  classification is cited; a non-null deadline is cited; a manual-review route
  carries the rule citation that justified it (`ambiguous_rule` or
  `unsupported_rule`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from evals.contract import CaseOutcome, Check, RunData

NAME = "grounding"

CITATION_EXACT = "grounding.citation_exact"
"""Name of the exact-quote check."""

CLAIM_SOURCES = "grounding.claim_sources"
"""Name of the claim-coverage check."""

_SUPPORTED_CLASSIFICATIONS = frozenset(
    {"unauthorized", "duplicate_charge", "service_not_received"}
)
"""Classifications whose choice must be justified by a citation."""

_DEADLINE_CLAIM = "deadline"
_ROUTING_CLAIM = "routing"
_CLASSIFICATION_CLAIM = "classification"
_MANUAL_REVIEW = "manual_review"
_RULE_CLAIMS = frozenset({"ambiguous_rule", "unsupported_rule"})
"""The rule claims that justify sending a case to a person."""

_MANUAL_REVIEW_REQUIREMENT = "manual_review_rule"
"""Requirement name reported when the manual-review rule citation is absent."""


def run(run: RunData) -> list[Check]:
    """Return the grounding checks for every case."""
    checks: list[Check] = []
    for case in run.cases:
        contract = case.contract
        if not isinstance(contract, Mapping):
            checks.extend(_unbuilt_checks(case))
            continue
        checks.append(_citation_exact(case, contract, run.sources))
        checks.append(_claim_sources(case, contract))
    return checks


def _unbuilt_checks(case: CaseOutcome) -> list[Check]:
    """Return the two failing checks a case with no contract earns."""
    reason = (
        f"case not built: {case.build_error}"
        if case.build_error
        else "case has no contract to score"
    )
    evidence = {"build_error": case.build_error}
    return [
        Check(CITATION_EXACT, case.case_id, False, reason, dict(evidence)),
        Check(CLAIM_SOURCES, case.case_id, False, reason, dict(evidence)),
    ]


def _citation_entries(contract: Mapping[str, Any]) -> list[Any]:
    """Return the contract citations as a list, empty when absent or malformed."""
    raw = contract.get("citations")
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return list(raw)
    return []


def _invalid_citations(
    citations: Sequence[Any], sources: Mapping[str, str]
) -> list[dict[str, Any]]:
    """Return one evidence row per citation that does not resolve to its source."""
    invalid: list[dict[str, Any]] = []
    for index, item in enumerate(citations):
        if not isinstance(item, Mapping):
            invalid.append(
                {
                    "index": index,
                    "claim": None,
                    "source_id": None,
                    "quote": None,
                    "reason": "citation is not an object",
                }
            )
            continue
        source_id = item.get("source_id")
        quote = item.get("quote")
        reason: str | None = None
        if not isinstance(source_id, str) or source_id not in sources:
            reason = f"unknown source id: {source_id!r}"
        elif not isinstance(quote, str) or not quote.strip():
            reason = "quote is not a non-empty string"
        elif quote not in sources[source_id]:
            reason = "quote is not an exact substring of its source"
        if reason is not None:
            invalid.append(
                {
                    "index": index,
                    "claim": item.get("claim"),
                    "source_id": source_id,
                    "quote": quote,
                    "reason": reason,
                }
            )
    return invalid


def _citation_exact(
    case: CaseOutcome, contract: Mapping[str, Any], sources: Mapping[str, str]
) -> Check:
    """Return the exact-quote check: every citation resolves to a real quote."""
    citations = _citation_entries(contract)
    invalid = _invalid_citations(citations, sources)
    evidence = {"citations": len(citations), "invalid": invalid}
    if not citations:
        return Check(
            CITATION_EXACT,
            case.case_id,
            False,
            "no citations: at least one is required",
            evidence,
        )
    if invalid:
        first = invalid[0]["reason"]
        return Check(
            CITATION_EXACT,
            case.case_id,
            False,
            f"{len(invalid)} of {len(citations)} citations are invalid, first: {first}",
            evidence,
        )
    return Check(
        CITATION_EXACT,
        case.case_id,
        True,
        f"all {len(citations)} citations quote their source exactly",
        evidence,
    )


def _claims_present(citations: Sequence[Any]) -> list[str]:
    """Return the distinct string claim names, sorted for a stable reason."""
    claims = {
        item["claim"]
        for item in citations
        if isinstance(item, Mapping) and isinstance(item.get("claim"), str)
    }
    return sorted(claims)


def _missing_requirements(contract: Mapping[str, Any], claims: list[str]) -> list[str]:
    """Return the requirement names the contract does not cite."""
    present = set(claims)
    missing: list[str] = []
    if _ROUTING_CLAIM not in present:
        missing.append(_ROUTING_CLAIM)
    classification = contract.get("classification")
    if (
        isinstance(classification, str)
        and classification in _SUPPORTED_CLASSIFICATIONS
        and _CLASSIFICATION_CLAIM not in present
    ):
        missing.append(_CLASSIFICATION_CLAIM)
    if contract.get("deadline") is not None and _DEADLINE_CLAIM not in present:
        missing.append(_DEADLINE_CLAIM)
    if contract.get("routing") == _MANUAL_REVIEW and not present & _RULE_CLAIMS:
        missing.append(_MANUAL_REVIEW_REQUIREMENT)
    missing.sort()
    return missing


def _claim_sources(case: CaseOutcome, contract: Mapping[str, Any]) -> Check:
    """Return the claim-coverage check: every required claim carries a citation."""
    claims = _claims_present(_citation_entries(contract))
    missing = _missing_requirements(contract, claims)
    evidence = {"claims": claims, "missing": missing}
    if missing:
        return Check(
            CLAIM_SOURCES,
            case.case_id,
            False,
            f"missing claim citations: {', '.join(missing)}",
            evidence,
        )
    return Check(
        CLAIM_SOURCES,
        case.case_id,
        True,
        "every required claim is cited",
        evidence,
    )
