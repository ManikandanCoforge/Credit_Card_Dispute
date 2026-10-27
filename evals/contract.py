"""The records every metric reads and writes.

One `Check` is one metric verdict for one case. One `CaseOutcome` is what the
application produced for one case plus that case's audit rows. One `RunData`
is the whole set: the dataset, the gold, the outcomes and the run identity.

A metric receives a `RunData` and returns checks; it never mutates the run.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Check:
    """One metric verdict, with the evidence behind it."""

    metric: str
    case_id: str
    passed: bool
    reason: str
    evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CaseOutcome:
    """What the application produced for one case, plus that case's audit rows."""

    case_id: str
    tools: tuple[str, ...]
    documents: tuple[str, ...]
    gold: Mapping[str, Any]
    contract: Mapping[str, Any] | None
    build_error: str | None
    audit: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class RunData:
    """One evaluation set, ready to score."""

    set_name: str
    data_dir: Path
    gold_path: Path
    dataset: Mapping[str, Any]
    gold: Mapping[str, Mapping[str, Any]]
    sources: Mapping[str, str]
    cases: tuple[CaseOutcome, ...]
    audit: tuple[Mapping[str, Any], ...]
    format_errors: tuple[str, ...]
    commit: str
    started_at: str
    base_url: str

    def submissions(self) -> list[Mapping[str, Any]]:
        """Return the submission array: built contracts, in bank order."""
        return [case.contract for case in self.cases if case.contract is not None]
