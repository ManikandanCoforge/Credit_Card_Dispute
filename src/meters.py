"""Record one JSON meter line per case.

A case run calls record_case_meter after the case finishes. This module does
not run a case.
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict


class LatencyPercentiles(TypedDict):
    """Nearest-rank latency percentiles read from a meter file."""

    p50: int
    p95: int


class MeterLeak(Exception):
    """The meter line would have contained evidence text or a restricted number."""


# An account number or a card number is a run of ten or more digits.
_ACCOUNT_OR_CARD_NUMBER = re.compile(r"\d{10,}")
# The package's synthetic private token, refused whole rather than copied from gold.
_RESTRICTED_VALUE = "SYNTHETIC-PRIVATE"


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
    """Append one JSON meter line for a finished case."""
    _reject_leaks(case_id, route)
    line = {
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
    with path.open("a", encoding="utf-8") as meter_file:
        meter_file.write(json.dumps(line, ensure_ascii=False) + "\n")


def latency_percentiles(path: Path) -> LatencyPercentiles:
    """Return nearest-rank p50 and p95 of latency_ms from the meter file."""
    latencies = [
        int(json.loads(line)["latency_ms"])
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    return {"p50": _nearest_rank(latencies, 50), "p95": _nearest_rank(latencies, 95)}


def _reject_leaks(case_id: str, route: str) -> None:
    text = case_id + route
    if (
        any(character.isspace() for character in text)
        or _ACCOUNT_OR_CARD_NUMBER.search(text)
        or _RESTRICTED_VALUE in text
    ):
        raise MeterLeak


def _nearest_rank(values: list[int], percent: int) -> int:
    ordered = sorted(values)
    rank = max(1, (percent * len(ordered) + 99) // 100)
    return ordered[rank - 1]


def _started_at(started_at: datetime) -> str:
    utc = started_at.astimezone(UTC)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"
