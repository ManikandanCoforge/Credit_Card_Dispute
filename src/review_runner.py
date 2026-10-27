"""Open a human review for each finished draft, then record the approved ones.

submit
  load_contract_results: one draft per case, read from the bank
  for each built draft
    submit_review: POST /v1/reviews; the review id and draft hash are kept with the draft
  write the journal
check
  read the journal
  until every review is decided, or the wait runs out
    review_alert: GET /v1/reviews/{review_id}; an approval of the unchanged draft
    creates the record once, keyed case_id:review_id
  write the journal

The reviewer decides in another terminal with the operator command. Nothing here
runs that command, and no record is written without an approval of the unchanged
draft. The wait is bounded: each pending review is read once per interval, and the
check stops when the wait runs out, leaving undecided reviews pending in the journal.
"""

import argparse
import json
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TypedDict

from src.contract_records import (
    ContractResult,
    ToolRetry,
    build_contract_result,
    contract_case_plans,
)
from src.idempotency import CreateRejected, MissingRecord
from src.load_records import CaseListError
from src.review_gate import ReviewRefused, review_alert, submit_review

_DEFAULT_BASE_URL = "http://127.0.0.1:8765"
_DEFAULT_JOURNAL = Path("reports") / "reviews.json"
# How long check waits for the reviewer by default, and how often it reads each review.
_DEFAULT_WAIT_SECONDS = 60.0
_POLL_INTERVAL_SECONDS = 2.0
# A review the bank could not be reached for is read again on the next poll.
_RETRY_LATER = "unreachable"


class JournalEntry(TypedDict):
    """One submitted draft and what the reviewer has decided about it so far.

    status is pending, recorded (this check created the record), already_recorded
    (the complaint had its record already), rejected (the draft goes back to the
    analyst) or refused (the gate stopped it without a write; reason says why).
    """

    case_id: str
    review_id: str
    draft_hash: str
    draft: dict[str, object]
    status: str
    record_id: str | None
    reason: str | None


def submit_drafts(
    base_url: str,
    data_dir: str | Path,
    cases: Sequence[str] = (),
    retry: ToolRetry | None = None,
) -> tuple[list[JournalEntry], list[ContractResult]]:
    """Open one review for each built draft, and return the entries and the unbuilt cases.

    cases, when given, limits the run to those case ids; no other case's tools are
    read. Every built draft is submitted, whatever its routing: the reviewer decides
    whether a case is created.
    """
    shared = ToolRetry() if retry is None else retry
    results = [
        build_contract_result(plan, base_url, data_dir, retry=shared)
        for plan in contract_case_plans(base_url, data_dir)
        if not cases or plan["record"]["case_id"] in cases
    ]
    entries: list[JournalEntry] = []
    for result in results:
        contract = result["contract"]
        if contract is None:
            continue
        draft: dict[str, object] = dict(contract)
        submitted = submit_review(base_url, result["case_id"], draft)
        entries.append(
            {
                "case_id": result["case_id"],
                "review_id": submitted["review_id"],
                "draft_hash": submitted["draft_hash"],
                "draft": draft,
                "status": "pending",
                "record_id": None,
                "reason": None,
            }
        )
    return entries, [result for result in results if result["contract"] is None]


def check_reviews(
    base_url: str,
    entries: Sequence[JournalEntry],
    *,
    wait_seconds: float = _DEFAULT_WAIT_SECONDS,
    interval: float = _POLL_INTERVAL_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> list[JournalEntry]:
    """Read each pending review until all are decided or wait_seconds has passed.

    Every pending review is read at least once. A decided entry is never read again,
    so an approved draft is recorded once, however often check runs.
    """
    deadline = clock() + wait_seconds
    current = list(entries)
    while True:
        current = [
            _check(base_url, entry) if entry["status"] == "pending" else entry
            for entry in current
        ]
        remaining = deadline - clock()
        if all(entry["status"] != "pending" for entry in current) or remaining <= 0:
            return current
        sleep(min(interval, remaining))


def read_journal(path: Path) -> list[JournalEntry]:
    entries: list[JournalEntry] = json.loads(path.read_text(encoding="utf-8"))
    return entries


def write_journal(path: Path, entries: Sequence[JournalEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(entries), indent=2) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> None:
    """submit opens the reviews; check reads them, bounded, and records the approved ones.

    submit exits 1 when a case was not built. check exits 1 while any review is
    pending or was refused, so an undecided run is never mistaken for a finished one.
    """
    args = _parser().parse_args(argv)
    if args.command == "submit":
        _submit(args)
    else:
        _check_journal(args)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Open a human review for each finished draft, then record the approved ones."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    submit = commands.add_parser("submit", help="Open a review for each finished draft.")
    submit.add_argument("--base-url", default=_DEFAULT_BASE_URL)
    submit.add_argument("--data", default="data/dev")
    submit.add_argument("--journal", type=Path, default=_DEFAULT_JOURNAL)
    submit.add_argument("--case", action="append", default=[], help="Only this case id.")
    check = commands.add_parser("check", help="Record the drafts the reviewer approved.")
    check.add_argument("--base-url", default=_DEFAULT_BASE_URL)
    check.add_argument("--journal", type=Path, default=_DEFAULT_JOURNAL)
    check.add_argument("--wait", type=float, default=_DEFAULT_WAIT_SECONDS)
    return parser


def _submit(args: argparse.Namespace) -> None:
    try:
        entries, unbuilt = submit_drafts(args.base_url, args.data, args.case)
    except CaseListError:
        sys.stderr.write("the bank case list could not be read\n")
        raise SystemExit(1) from None
    except ReviewRefused as error:
        sys.stderr.write(f"a review could not be opened: {error.reason}\n")
        raise SystemExit(1) from None
    write_journal(args.journal, entries)
    for entry in entries:
        routing = entry["draft"]["routing"]
        sys.stdout.write(f"{entry['case_id']}: review {entry['review_id']} pending ({routing})\n")
    for result in unbuilt:
        sys.stderr.write(f"{result['case_id']}: not built: {result['error']}\n")
    if unbuilt:
        raise SystemExit(1)


def _check_journal(args: argparse.Namespace) -> None:
    entries = check_reviews(args.base_url, read_journal(args.journal), wait_seconds=args.wait)
    write_journal(args.journal, entries)
    for entry in entries:
        sys.stdout.write(f"{entry['case_id']}: {_outcome(entry)}\n")
    if any(entry["status"] in {"pending", "refused"} for entry in entries):
        raise SystemExit(1)


def _outcome(entry: JournalEntry) -> str:
    if entry["status"] in {"recorded", "already_recorded"}:
        return f"{entry['status']} as {entry['record_id']}"
    if entry["status"] == "rejected":
        return "rejected; the draft goes back to the analyst"
    if entry["status"] == "refused":
        return f"refused ({entry['reason']}); nothing was written"
    return f"review {entry['review_id']} still pending"


def _check(base_url: str, entry: JournalEntry) -> JournalEntry:
    """Read one pending review once and record what it says."""
    try:
        alert = review_alert(
            base_url,
            entry["case_id"],
            entry["draft"],
            review_id=entry["review_id"],
            draft_hash=entry["draft_hash"],
        )
    except ReviewRefused as error:
        if error.reason == _RETRY_LATER:
            return entry
        return {**entry, "status": "refused", "reason": error.reason}
    except (CreateRejected, MissingRecord) as error:
        return {**entry, "status": "refused", "reason": str(error)}
    if alert["alert"] == "submit_record":
        status = "recorded" if alert.get("created") else "already_recorded"
        return {**entry, "status": status, "record_id": alert.get("record_id")}
    if alert["alert"] == "rejected":
        return {**entry, "status": "rejected"}
    return entry


if __name__ == "__main__":
    main()
