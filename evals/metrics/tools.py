"""Tool-call correctness: read from the mock audit, never from the dataset.

Owned by the tool-call metric. Checks per case:

* `tools.required_reads` -- every tool the dataset declares was read and at
  least one attempt answered 200.
* `tools.no_forbidden_writes` -- no audit event is a write or record creation.
* `tools.retry_bound` -- no tool had more than three total attempts (the first
  attempt plus two retries is the contract).
* `tools.no_extra_reads` -- no tool was read that the dataset did not declare.

The verdict comes from `CaseOutcome.audit` alone. `CaseOutcome.tools` names the
expectation, which the runner fills from the dataset; the audit proves what the
application actually asked for. Nothing here reads `RunData.dataset`.

`attempts` in the evidence maps a tool name to one status per recorded attempt,
in audit order, so its length is the attempt count. A tool read whose detail
carries no usable tool name is counted under `UNNAMED_TOOL`: no case can
declare that name, so it fails `no_extra_reads` and is credited to no required
read. An audit event outside `WRITE_EVENTS` is ignored by every check.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from evals.contract import CaseOutcome, Check, RunData

NAME = "tools"

REQUIRED_READS = "tools.required_reads"
NO_FORBIDDEN_WRITES = "tools.no_forbidden_writes"
RETRY_BOUND = "tools.retry_bound"
NO_EXTRA_READS = "tools.no_extra_reads"

MAX_ATTEMPTS_PER_TOOL = 3
"""Total attempts allowed per tool: the first attempt plus two retries."""

UNNAMED_TOOL = "<unnamed>"
"""Stand-in for a tool read whose audit detail names no tool."""

WRITE_EVENTS = frozenset(
    {
        "record_created",
        "forbidden_write_attempt",
        "unapproved_write_attempt",
        "unsupported_write_attempt",
        "write_replayed",
        "duplicate_prevented",
        "idempotency_conflict",
    }
)


@dataclass(frozen=True)
class _Read:
    """One audit row that recorded a tool read."""

    tool: str
    attempt: object
    status: object

    def evidence(self) -> dict[str, object]:
        """Return this read as report evidence."""
        return {"tool": self.tool, "attempt": self.attempt, "status": self.status}


def run(run: RunData) -> list[Check]:
    """Return the tool-call checks for every case."""
    checks: list[Check] = []
    for case in run.cases:
        reads = _reads(case)
        attempts = _attempts(reads)
        declared = tuple(dict.fromkeys(case.tools))
        checks.extend(
            [
                _required_reads(case.case_id, declared, reads, attempts),
                _no_forbidden_writes(case.case_id, case.audit),
                _retry_bound(case.case_id, attempts),
                _no_extra_reads(case.case_id, declared, reads, attempts),
            ]
        )
    return checks


def _required_reads(
    case_id: str,
    declared: Sequence[str],
    reads: Sequence[_Read],
    attempts: Mapping[str, Sequence[object]],
) -> Check:
    """Require at least one 200 read for every tool the case declares."""
    evidence: dict[str, Any] = {
        "declared_tools": list(declared),
        "attempts": _status_map(attempts),
        "missing": [],
    }
    if not declared:
        return Check(
            REQUIRED_READS, case_id, True, "no tool is declared for this case", evidence
        )
    missing = [
        tool
        for tool in declared
        if not any(_answered(status) for status in attempts.get(tool, ()))
    ]
    evidence["missing"] = missing
    if not missing:
        return Check(
            REQUIRED_READS,
            case_id,
            True,
            f"{_listed(declared)} answered 200",
            evidence,
        )
    if not reads:
        reason = f"no tool read was recorded for {_listed(missing)}"
    else:
        reason = "; ".join(
            _missing_reason(tool, attempts.get(tool, ())) for tool in missing
        )
    return Check(REQUIRED_READS, case_id, False, reason, evidence)


def _no_forbidden_writes(case_id: str, audit: Sequence[Mapping[str, Any]]) -> Check:
    """Reject any audit event whose name is a write or a record creation."""
    names: list[str] = []
    offending: list[dict[str, Any]] = []
    for row in audit:
        event = _event(row)
        if event in WRITE_EVENTS:
            names.append(event)
            offending.append(dict(row))
    evidence = {"write_events": sorted(WRITE_EVENTS), "offending": offending}
    if offending:
        return Check(
            NO_FORBIDDEN_WRITES,
            case_id,
            False,
            f"write events in the audit: {_listed(list(dict.fromkeys(names)))}",
            evidence,
        )
    return Check(
        NO_FORBIDDEN_WRITES, case_id, True, "no write event in the audit", evidence
    )


def _retry_bound(case_id: str, attempts: Mapping[str, Sequence[object]]) -> Check:
    """Reject a tool attempted more often than the retry contract allows."""
    over_limit = {
        tool: len(statuses)
        for tool, statuses in attempts.items()
        if len(statuses) > MAX_ATTEMPTS_PER_TOOL
    }
    evidence: dict[str, Any] = {
        "limit": MAX_ATTEMPTS_PER_TOOL,
        "attempts": _status_map(attempts),
        "over_limit": over_limit,
    }
    if over_limit:
        reason = "; ".join(
            f"{tool} was read {count} times (limit {MAX_ATTEMPTS_PER_TOOL})"
            for tool, count in over_limit.items()
        )
        return Check(RETRY_BOUND, case_id, False, reason, evidence)
    return Check(
        RETRY_BOUND,
        case_id,
        True,
        f"every tool was read at most {MAX_ATTEMPTS_PER_TOOL} times",
        evidence,
    )


def _no_extra_reads(
    case_id: str,
    declared: Sequence[str],
    reads: Sequence[_Read],
    attempts: Mapping[str, Sequence[object]],
) -> Check:
    """Reject a tool read the case does not declare."""
    declared_set = set(declared)
    extra = [tool for tool in attempts if tool not in declared_set]
    evidence: dict[str, Any] = {
        "declared_tools": list(declared),
        "attempts": _status_map(attempts),
        "extra_tools": extra,
        "offending": [read.evidence() for read in reads if read.tool not in declared_set],
    }
    if extra:
        return Check(
            NO_EXTRA_READS,
            case_id,
            False,
            f"undeclared tools were read: {_listed(extra)}",
            evidence,
        )
    return Check(
        NO_EXTRA_READS, case_id, True, "every tool read was declared", evidence
    )


def _reads(case: CaseOutcome) -> list[_Read]:
    """Return this case's tool reads, in recorded order."""
    return [_read(row) for row in case.audit if _event(row) == "tool_read"]


def _read(row: Mapping[str, Any]) -> _Read:
    """Return one tool_read row as a read, naming a missing tool."""
    detail = row.get("detail")
    fields: Mapping[str, Any] = detail if isinstance(detail, Mapping) else {}
    tool = fields.get("tool")
    return _Read(
        tool=tool if isinstance(tool, str) and tool else UNNAMED_TOOL,
        attempt=fields.get("attempt"),
        status=fields.get("status"),
    )


def _event(row: Mapping[str, Any]) -> str:
    """Return the audit event name, or an empty string when it is not a name."""
    event = row.get("event")
    return event if isinstance(event, str) else ""


def _attempts(reads: Sequence[_Read]) -> dict[str, list[object]]:
    """Return one status per attempt, keyed by tool in first-seen order."""
    attempts: dict[str, list[object]] = {}
    for read in reads:
        attempts.setdefault(read.tool, []).append(read.status)
    return attempts


def _status_map(attempts: Mapping[str, Sequence[object]]) -> dict[str, list[object]]:
    """Return the attempts evidence as plain lists, not tuples or views."""
    return {tool: list(statuses) for tool, statuses in attempts.items()}


def _answered(status: object) -> bool:
    """Return True when a recorded status says the read was answered."""
    return status == 200 or status == "200"


def _missing_reason(tool: str, statuses: Sequence[object]) -> str:
    """Return why one declared tool did not satisfy required_reads."""
    if not statuses:
        return f"{tool} was never read"
    return f"{tool} never answered 200 (attempts: {_statuses(statuses)})"


def _statuses(statuses: Sequence[object]) -> str:
    """Return the recorded statuses of one tool as prose."""
    return ", ".join("unknown" if status is None else str(status) for status in statuses)


def _listed(names: Sequence[str]) -> str:
    """Return names as prose: one name, or a comma list with a final 'and'."""
    if len(names) <= 1:
        return names[0] if names else ""
    return f"{', '.join(names[:-1])} and {names[-1]}"

