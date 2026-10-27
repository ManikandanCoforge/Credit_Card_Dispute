"""Which models may answer the hybrid's questions: qualification records and scoring (ADR-003).

A provider and model pair is used only when models.toml holds a passed record for the
current SCHEMA_HASH. tools/qualify_model.py makes a record: it asks the model the
dispute-type question for every case in evals/qualification and scores each answer
against expectations that were fixed before any model ran.

  correct   the proposed type gives the expected classification (cash_withdrawal and
            other_dispute both give unsupported), or "none" or no usable answer where the
            expected answer is ambiguous, because abstaining is right there
  cautious  "none" or no usable answer where a type was expected, or an unsupported type
            where a supported one or an abstention was expected: the case goes to a
            person, which is safe but slower
  unsafe    a supported type that is wrong, which could reach ready_for_review

A record passes only with zero unsafe answers and at least 90% of the cases answered.
"""

import statistics
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict

from src.model_cue import SCHEMA_HASH

SUPPORTED = ("unauthorized", "duplicate_charge", "service_not_received")
TYPE_TO_CLASS = {
    "unauthorized": "unauthorized",
    "duplicate_charge": "duplicate_charge",
    "service_not_received": "service_not_received",
    "cash_withdrawal": "unsupported",
    "other_dispute": "unsupported",
}
MIN_ANSWERED = 0.9


class QualificationRow(TypedDict):
    """One qualification case: what was expected, what the model proposed, and how it scored."""

    case_id: str
    expected: str
    gap: bool
    proposal: str | None
    outcome: str
    answered: bool
    latency_ms: float | None


class QualificationRecord(TypedDict):
    """One models.toml entry. passed decides whether the pair may be used."""

    provider: str
    model_id: str
    schema_hash: str
    qualified_on: str
    cases: int
    answered: int
    cue_correct: int
    cautious: int
    unsafe: int
    gap_cases: int
    gap_correct: int
    median_latency_s: float | None
    data_location: str
    approved_by: str
    passed: bool


def load_registry(path: Path) -> list[dict[str, object]]:
    """Every [[model]] entry in the registry, or none when the file does not exist."""
    if not path.is_file():
        return []
    with path.open("rb") as stream:
        entries = tomllib.load(stream).get("model", [])
    return [entry for entry in entries if isinstance(entry, dict)]


def find_qualified(
    entries: Sequence[dict[str, object]],
    provider: str,
    model_id: str,
    schema_hash: str = SCHEMA_HASH,
) -> dict[str, object] | None:
    """The passed record for this provider, model and schema, or None."""
    return next(
        (
            entry
            for entry in entries
            if entry.get("provider") == provider
            and entry.get("model_id") == model_id
            and entry.get("schema_hash") == schema_hash
            and entry.get("passed") is True
        ),
        None,
    )


def score(expected: str, proposal: str | None) -> str:
    """correct, cautious or unsafe, for one proposed type against the expected classification."""
    if proposal is None or proposal == "none":
        return "correct" if expected == "ambiguous" else "cautious"
    got = TYPE_TO_CLASS.get(proposal)
    if got == expected:
        return "correct"
    return "unsafe" if got in SUPPORTED else "cautious"


def summarize(
    rows: Sequence[QualificationRow],
    *,
    provider: str,
    model_id: str,
    qualified_on: str,
    data_location: str,
    approved_by: str,
) -> QualificationRecord:
    """The registry record for a qualification run, with passed decided by the fixed bar."""
    latencies = [row["latency_ms"] for row in rows if row["latency_ms"] is not None]
    gap_rows = [row for row in rows if row["gap"]]
    answered = sum(1 for row in rows if row["answered"])
    unsafe = sum(1 for row in rows if row["outcome"] == "unsafe")
    return {
        "provider": provider,
        "model_id": model_id,
        "schema_hash": SCHEMA_HASH,
        "qualified_on": qualified_on,
        "cases": len(rows),
        "answered": answered,
        "cue_correct": sum(1 for row in rows if row["outcome"] == "correct"),
        "cautious": sum(1 for row in rows if row["outcome"] == "cautious"),
        "unsafe": unsafe,
        "gap_cases": len(gap_rows),
        "gap_correct": sum(1 for row in gap_rows if row["outcome"] == "correct"),
        "median_latency_s": (
            round(statistics.median(latencies) / 1000, 3) if latencies else None
        ),
        "data_location": data_location,
        "approved_by": approved_by,
        "passed": bool(rows) and unsafe == 0 and answered >= MIN_ANSWERED * len(rows),
    }
