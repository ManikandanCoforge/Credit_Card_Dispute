"""Record one JSON meter line per case.

A case run calls record_case_meter after the case finishes. This module does
not run a case.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from src.untrusted import restricted_values


class LatencyPercentiles(TypedDict):
    """Nearest-rank latency percentiles read from a meter file.

    Both are None when the meter file holds no case, so a zero-case run reports
    a missing latency instead of raising.
    """

    p50: int | None
    p95: int | None


class CaseAttempts(TypedDict):
    """The tool attempts and retries one case's meter line recorded."""

    tool_attempts: int
    retry_count: int


class MeterLeak(Exception):
    """The meter line would have contained evidence text or a restricted value."""


def record_case_meter(
    path: Path,
    *,
    case_id: str,
    route: str,
    started_at: datetime,
    latency_ms: int,
    model_calls: int,
    input_tokens: int,
    output_tokens: int,
    tool_attempts: int,
    retry_count: int,
) -> None:
    """Append one JSON meter line for a finished case.

    The line is refused, and the file left unchanged, when any field would carry
    evidence text or a restricted value.
    """
    line: dict[str, object] = {
        "case_id": case_id,
        "route": route,
        "started_at": _started_at(started_at),
        "latency_ms": latency_ms,
        "model_calls": model_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "tool_attempts": tool_attempts,
        "retry_count": retry_count,
    }
    _reject_leaks(line)
    with path.open("a", encoding="utf-8") as meter_file:
        meter_file.write(json.dumps(line, ensure_ascii=False) + "\n")


def latency_percentiles(path: Path) -> LatencyPercentiles:
    """Return nearest-rank p50 and p95 of latency_ms from the meter file.

    Returns None for both when the file holds no line, which is what a run over
    an empty case list writes, so the caller reports a missing latency instead
    of raising IndexError.
    """
    latencies = [
        int(json.loads(line)["latency_ms"])
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    if not latencies:
        return {"p50": None, "p95": None}
    return {"p50": _nearest_rank(latencies, 50), "p95": _nearest_rank(latencies, 95)}


def case_attempts(path: Path) -> dict[str, CaseAttempts]:
    """Return each case's tool attempts and retries from the meter file.

    Args:
        path: The redacted meter file the run wrote.

    Returns:
        A mapping from case id to its recorded tool_attempts and retry_count.
        A case with no line is absent, so the caller can show it as unknown
        instead of inventing a count.
    """
    attempts: dict[str, CaseAttempts] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        attempts[row["case_id"]] = {
            "tool_attempts": int(row["tool_attempts"]),
            "retry_count": int(row["retry_count"]),
        }
    return attempts


def _reject_leaks(line: dict[str, object]) -> None:
    """Raise MeterLeak when any field would carry evidence text or a restricted value.

    The restricted-value detector is the one src/untrusted.py already uses for
    model prompts and log lines, so a grouped, dotted, full-width or zero-width
    card number is caught in any field, and a card carried as an integer too.
    """
    if any(
        isinstance(value, str) and any(character.isspace() for character in value)
        for value in line.values()
    ):
        raise MeterLeak
    if restricted_values(line):
        raise MeterLeak


def _nearest_rank(values: list[int], percent: int) -> int:
    ordered = sorted(values)
    rank = max(1, (percent * len(ordered) + 99) // 100)
    return ordered[rank - 1]


def _started_at(started_at: datetime) -> str:
    utc = started_at.astimezone(UTC)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"
