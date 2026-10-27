"""Run every dev case through the live mock and publish a scored report.

The run uses the production read path in src.contract_records: the case list is
read once, then each case's documents and tools are read and its contract
assembled while time.perf_counter measures that case. The submission is scored
with tools.evaluate.evaluate in process, so no second evaluator exists here.

Artifacts:
  reports/scored-run.json         machine-readable run report
  reports/scored-run-meters.json  one measured meter row per case
  reports/meters.jsonl            one redacted meter line per case
  reports/scored-run.md           human-readable report
  submissions/scored-run.json     the evaluator submission array

Exit status is 0 only when every case in the case list passes. Every artifact
is still written when they do not. When the case list cannot be read, nothing
is written and the exit status is 1, so an unreachable bank never replaces the
committed report with an empty one.
"""

import argparse
import json

# Runs git to record the commit the report was produced from.
import subprocess  # nosec B404
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.contract import Contract
from src.contract_records import (
    CasePlan,
    ContractResult,
    build_contract_result,
    contract_case_plans,
)
from src.load_records import BankReadError
from tools.evaluate import evaluate

EXPECTED_CASES = 12
DETERMINISTIC_PATH = "deterministic_template"
EXCEPTION_STATUS = "proposed_pending_pod_agreement"

# The failing dev cases that a later ticket is expected to fix. This is a
# proposal for pod agreement, not agreed scope, and it never changes a result.
_PROPOSED_EXCEPTIONS: dict[str, tuple[str, str]] = {
    "CARD-D05": (
        "COF-39",
        (
            "A conflicting follow-up is not read, so the ambiguous conflict is "
            "not classified. Conflict and unsupported handling is COF-39."
        ),
    ),
    "CARD-D06": (
        "COF-39",
        (
            "An unsupported cash-withdrawal classification is not emitted. "
            "Conflict and unsupported handling is COF-39."
        ),
    ),
    "CARD-D07": (
        "COF-40",
        (
            "A persistent transaction failure stops the case instead of routing "
            "to manual_review with null facts. Retry and outage handling is COF-40."
        ),
    ),
    "CARD-D09": (
        "COF-43",
        (
            "The joined statement is not an exact intake excerpt, so the duplicate "
            "redelivery is not built. Duplicate intake and narrative work is COF-43."
        ),
    ),
    "CARD-D10": (
        "COF-40",
        (
            "A transient transaction fault is not retried, so the case is not "
            "built. Retry is COF-40."
        ),
    ),
}


class MeasuredCase(TypedDict):
    """One case after its evidence reads were timed."""

    case_id: str
    duration_ms: float
    contract: Contract | None
    error: str | None


class CaseReport(TypedDict):
    """One case in the published report, merged with the evaluator's checks."""

    case_id: str
    submitted: bool
    passed: bool
    duration_ms: float
    failed_checks: list[str]
    error: str | None


class MeterRow(TypedDict):
    """One measured row in reports/scored-run-meters.json."""

    case_id: str
    duration_ms: float
    model_calls: int
    model_tokens_in: int
    model_tokens_out: int
    cost_usd: float
    path: str


class ExceptionEntry(TypedDict):
    """One proposed, not yet agreed, failing-case exception."""

    case_id: str
    ticket: str
    status: str
    failed_checks: list[str]
    error: str | None
    note: str


def p95_nearest_rank(durations: Sequence[float]) -> float | None:
    """Return the nearest-rank 95th percentile, or None when nothing was measured.

    Rank is ceil(0.95 * n), computed with integers so the result is exactly
    reproducible and does not depend on floating-point rounding. Over the twelve
    measured cases the rank is twelve, which is the slowest case.
    """
    values = sorted(durations)
    if not values:
        return None
    rank = max(1, (95 * len(values) + 99) // 100)
    return float(values[rank - 1])


def failed_checks(checks: Mapping[str, bool]) -> list[str]:
    """Every check that did not pass, sorted, without the boolean detail."""
    return sorted(name for name, passed in checks.items() if not passed)


def proposed_exception(
    case_id: str, failed_checks: Sequence[str] | None = None
) -> tuple[str, str] | None:
    """The pending ticket and note for a known failing case, or None.

    The mapping is intentionally narrow: it applies only when the case has no
    contract at all (the single failed check "submitted"). Any other failure of
    the same case is left unmapped so it stays visible as an unplanned failure
    instead of being excused.
    """
    mapping = _PROPOSED_EXCEPTIONS.get(case_id)
    if mapping is None:
        return None
    if failed_checks is not None and list(failed_checks) != ["submitted"]:
        return None
    return mapping


def measure_cases(
    plans: Sequence[CasePlan],
    base_url: str,
    data_dir: Path,
    *,
    build: Callable[[CasePlan], ContractResult] | None = None,
    meter_path: Path | None = None,
) -> list[MeasuredCase]:
    """Build each planned case and record its own elapsed milliseconds.

    The measurement wraps only that case's document and tool reads plus its
    assembly. The shared case-list read has already happened in the plans.

    build is an injection seam: production passes the bank-backed
    build_contract_result, and a test can pass a deterministic builder without
    a network.
    """
    if meter_path is not None and build is None:
        meter_path.parent.mkdir(parents=True, exist_ok=True)
        meter_path.write_text("", encoding="utf-8")
    builder = build if build is not None else (
        lambda plan: build_contract_result(plan, base_url, data_dir, meter_path=meter_path)
    )
    measured: list[MeasuredCase] = []
    for plan in plans:
        started = time.perf_counter()
        result = builder(plan)
        duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
        measured.append(
            {
                "case_id": result["case_id"],
                "duration_ms": duration_ms,
                "contract": result["contract"],
                "error": result["error"],
            }
        )
    return measured


def build_case_reports(
    measured: Sequence[MeasuredCase], evaluation: Mapping[str, Any]
) -> list[CaseReport]:
    """Merge measured durations with the evaluator's per-case checks.

    A case that could not be built has no submission, so the evaluator records
    the single failed check "submitted"; its error reason is kept beside it. A
    case the evaluator did not mention is a failure, never a silent pass.
    """
    evaluated = {case["case_id"]: case for case in evaluation["cases"]}
    reports: list[CaseReport] = []
    for case in measured:
        result = evaluated.get(case["case_id"])
        if result is None:
            checks: Mapping[str, bool] = {"missing_from_evaluation": False}
            passed = False
        else:
            checks = result["checks"]
            passed = bool(result["passed"])
        reports.append(
            {
                "case_id": case["case_id"],
                "submitted": case["contract"] is not None,
                "passed": passed,
                "duration_ms": case["duration_ms"],
                "failed_checks": failed_checks(checks),
                "error": case["error"],
            }
        )
    return reports


def meter_rows(case_reports: Sequence[CaseReport]) -> list[MeterRow]:
    """One measured meter row per case.

    The deterministic template path makes no model call, so these rows record 0
    model calls and 0 tokens and the cost is 0.00 USD by construction. That is
    the absence of a model path, not a measurement of one. No model price is
    assumed.
    """
    return [
        {
            "case_id": case["case_id"],
            "duration_ms": case["duration_ms"],
            "model_calls": 0,
            "model_tokens_in": 0,
            "model_tokens_out": 0,
            "cost_usd": 0.0,
            "path": DETERMINISTIC_PATH,
        }
        for case in case_reports
    ]


def exception_list(case_reports: Sequence[CaseReport]) -> list[ExceptionEntry]:
    """Document only failing cases that have a proposed ticket.

    Every entry is marked as pending pod agreement. Passing cases and failures
    with no mapped ticket are never included, so this list cannot hide a
    regression.
    """
    entries: list[ExceptionEntry] = []
    for case in case_reports:
        if case["passed"]:
            continue
        mapping = proposed_exception(case["case_id"], case["failed_checks"])
        if mapping is None:
            continue
        ticket, note = mapping
        entries.append(
            {
                "case_id": case["case_id"],
                "ticket": ticket,
                "status": EXCEPTION_STATUS,
                "failed_checks": list(case["failed_checks"]),
                "error": case["error"],
                "note": note,
            }
        )
    return entries


def unplanned_failures(case_reports: Sequence[CaseReport]) -> list[dict[str, Any]]:
    """Failing cases that have no proposed ticket, named so they stay visible."""
    return [
        {
            "case_id": case["case_id"],
            "failed_checks": list(case["failed_checks"]),
            "error": case["error"],
        }
        for case in case_reports
        if not case["passed"]
        and proposed_exception(case["case_id"], case["failed_checks"]) is None
    ]


def run_succeeded(report: Mapping[str, Any]) -> bool:
    """True only when every case in the case list passed with no format errors.

    The case count comes from the case list, not a hard-coded twelve, so the
    tool also works on a smaller fixture set. Twelve is the dev expectation and
    is asserted in the tests, not used as a gate here.
    """
    total = report["total_cases"]
    return total > 0 and report["pass_count"] == total and not report["format_errors"]


def assemble_report(
    case_reports: Sequence[CaseReport],
    evaluation: Mapping[str, Any],
    *,
    generated_at: str,
    git_commit: str,
    git_dirty: bool,
    base_url: str,
    dataset_name: str,
    meters: Sequence[MeterRow] | None = None,
) -> dict[str, Any]:
    """Assemble the scored-run report from measured cases and evaluator output.

    Cost and latency are read from the meter rows, the one artifact the report
    claims as their source. When meters are not supplied they are derived from
    the case reports, so a caller cannot silently report a different cost.
    """
    durations = [case["duration_ms"] for case in case_reports]
    total_cases = len(case_reports)
    meter_rows_used = list(meters) if meters is not None else meter_rows(case_reports)
    total_cost = round(sum(row["cost_usd"] for row in meter_rows_used), 6)
    return {
        "generated_at": generated_at,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "git_commit_note": (
            "HEAD at run time. "
            + (
                "The working tree had uncommitted changes when the artifacts "
                "were generated."
                if git_dirty
                else "The working tree was clean when the artifacts were generated."
            )
        ),
        "base_url": base_url,
        "dataset": dataset_name,
        "pass_count": sum(1 for case in case_reports if case["passed"]),
        "total_cases": total_cases,
        "format_errors": list(evaluation["format_errors"]),
        "p95_latency_ms": p95_nearest_rank(durations),
        "cost_per_case_usd": (
            0.0 if total_cases == 0 else round(total_cost / total_cases, 6)
        ),
        "total_cost_usd": total_cost,
        "cost_note": (
            "Read from reports/scored-run-meters.json. The deterministic template "
            "path makes no model call, so every row records 0 model calls and 0 "
            "tokens and the cost is 0.00 USD by construction, not by measurement. "
            "No model price is assumed or estimated."
        ),
        "cases": list(case_reports),
        "exceptions": exception_list(case_reports),
        "exception_status": EXCEPTION_STATUS,
        "exception_note": (
            "Proposed pending pod agreement. These are not agreed exceptions and "
            "they do not change any pass or fail result."
        ),
        "unplanned_failures": unplanned_failures(case_reports),
    }


def _md_cell(value: Any) -> str:
    """One markdown table cell, with pipes and newlines made harmless."""
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(report: Mapping[str, Any], meters: Sequence[MeterRow]) -> str:
    """Render the human-readable scored-run report."""
    total = report["total_cases"]
    lines = [
        "# Scored run across the twelve dev cases",
        "",
        (
            f"Generated at {report['generated_at']} from commit "
            f"`{report['git_commit']}` against `{report['base_url']}`."
            + (
                " The working tree had uncommitted changes when the report "
                "was generated."
                if report.get("git_dirty")
                else ""
            )
        ),
        f"Dataset: `{report['dataset']}`.",
        "",
        "## Result",
        "",
        f"- Pass: {report['pass_count']} / {total}",
        f"- Format errors: {len(report['format_errors'])}",
        (
            f"- p95 draft latency: {_fmt_ms(report['p95_latency_ms'])} "
            "(nearest-rank over the measured durations)"
        ),
        (
            f"- Cost per case: {report['cost_per_case_usd']:.2f} USD "
            "(0 model calls and 0 tokens in the meter file)"
        ),
        f"- Total cost: {report['total_cost_usd']:.2f} USD",
        "",
        "## Case results",
        "",
        "| Case | Submitted | Passed | Duration (ms) | Failed checks | Error |",
        "|---|---|---|---|---|---|",
    ]
    for case in report["cases"]:
        checks = ", ".join(case["failed_checks"]) or "-"
        lines.append(
            f"| {_md_cell(case['case_id'])} | {_bool(case['submitted'])} | "
            f"{_bool(case['passed'])} | {case['duration_ms']:.3f} | "
            f"{_md_cell(checks)} | {_md_cell(case['error'] or '-')} |"
        )

    failing = [case for case in report["cases"] if not case["passed"]]
    lines += [
        "",
        "## Failing cases",
        "",
    ]
    if failing:
        lines += [
            "| Case | Exact failed check(s) | Reason |",
            "|---|---|---|",
        ]
        for case in failing:
            lines.append(
                f"| {_md_cell(case['case_id'])} | "
                f"{_md_cell(', '.join(case['failed_checks']))} | "
                f"{_md_cell(case['error'] or '-')} |"
            )
    else:
        lines.append("None. Every case passed.")

    lines += [
        "",
        "## Exceptions (proposed, pending pod agreement)",
        "",
        (
            "**Status: proposed. These exceptions are not agreed scope.** Each "
            "one is tied to a later ticket and is excluded only from the "
            "expected-failure list, never from the pass count."
        ),
        "",
    ]
    if report["exceptions"]:
        lines += [
            "| Case | Ticket | Failed checks | Note |",
            "|---|---|---|---|",
        ]
        for entry in report["exceptions"]:
            lines.append(
                f"| {_md_cell(entry['case_id'])} | {_md_cell(entry['ticket'])} | "
                f"{_md_cell(', '.join(entry['failed_checks']))} | "
                f"{_md_cell(entry['note'])} |"
            )
    else:
        lines.append("None. No failing case has a proposed ticket.")
    if report["unplanned_failures"]:
        lines += [
            "",
            "### Unplanned failures (not exceptions)",
            "",
            "| Case | Failed checks | Reason |",
            "|---|---|---|",
        ]
        for entry in report["unplanned_failures"]:
            lines.append(
                f"| {_md_cell(entry['case_id'])} | "
                f"{_md_cell(', '.join(entry['failed_checks']))} | "
                f"{_md_cell(entry['error'] or '-')} |"
            )

    lines += [
        "",
        "## Metered cost",
        "",
        (
            "Latency and cost come from `reports/scored-run-meters.json`, one "
            "row per case. The path is `deterministic_template`, so "
            "`model_calls`, `model_tokens_in` and `model_tokens_out` are 0 and "
            "the cost is 0.00 USD by construction: this run wires no model call, "
            "so the meter shows what the run did, not what a model would cost."
        ),
        "",
        (
            "| Case | Duration (ms) | Calls | Tokens in | Tokens out | "
            "Cost (USD) | Path |"
        ),
        "|---|---|---|---|---|---|---|",
    ]
    for row in meters:
        lines.append(
            f"| {_md_cell(row['case_id'])} | {row['duration_ms']:.3f} | "
            f"{row['model_calls']} | {row['model_tokens_in']} | "
            f"{row['model_tokens_out']} | {row['cost_usd']:.2f} | "
            f"{_md_cell(row['path'])} |"
        )

    lines += [
        "",
        "## Reproduce",
        "",
        (
            "Run from the repository root, after `uv sync --locked`. The commands "
            "are the same on macOS, Linux and Windows. Use two terminals, and stop "
            "any other mock on port 8765 first."
        ),
        "",
        "In the first terminal, start the mock on a fresh state of its own:",
        "",
        "```sh",
        (
            "uv run --locked python tools/runtime.py reset --confirm "
            "--state .state/scored-run.sqlite"
        ),
        (
            "uv run --locked python tools/runtime.py serve --data data/dev --port 8765 "
            "--state .state/scored-run.sqlite"
        ),
        "```",
        "",
        "In the second terminal, run every case and score it:",
        "",
        "```sh",
        (
            "uv run --locked python tools/scored_run.py --base-url http://127.0.0.1:8765 "
            "--data data/dev --gold feedback/dev_gold.json"
        ),
        "```",
        "",
        (
            "The run exits 0 only when all twelve cases pass. A single transient "
            "fault fails once on a fresh state, so reset the state before each "
            "comparison. If the mock is not running, the run writes nothing and "
            "exits 1."
        ),
        "",
    ]
    return "\n".join(lines)


def _fmt_ms(value: float | None) -> str:
    """A millisecond value with three decimals, or a dash when nothing ran."""
    return "-" if value is None else f"{value:.3f} ms"


def _bool(value: bool) -> str:
    return "yes" if value else "no"


def utc_now() -> str:
    """The current UTC time as an ISO 8601 string with a Z suffix."""
    return (
        datetime.now(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def git_state(root: Path) -> tuple[str, bool]:
    """Return the HEAD commit and whether the working tree has changes."""
    # Fixed argv, never a shell, git from PATH.
    commit = subprocess.run(  # nosec B603 B607
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    status = subprocess.run(  # nosec B603 B607
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    sha = commit.stdout.strip() if commit.returncode == 0 else "unknown"
    return sha, bool(status.stdout.strip())


def _write_json(path: Path, value: Any) -> None:
    """Write one JSON artifact, creating its directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def run_scored(
    *,
    base_url: str,
    data_dir: Path,
    gold_path: Path,
    submission_path: Path,
    report_path: Path,
    meters_path: Path,
    markdown_path: Path,
    generated_at: str,
    git_commit: str,
    git_dirty: bool,
    case_meter_path: Path | None = None,
) -> int:
    """Run every case, score the submission and write every artifact.

    Returns 0 only when every case in the case list passes. The artifacts are
    written before the status is returned, so a failing run still publishes its
    numbers. When the case list cannot be read there are no numbers to publish:
    nothing is written, the reason goes to stderr, and the status is 1.
    """
    dataset = json.loads((data_dir / "dataset.json").read_text(encoding="utf-8"))
    gold = json.loads(gold_path.read_text(encoding="utf-8"))

    try:
        plans = contract_case_plans(base_url, data_dir)
    except (BankReadError, OSError) as error:
        print(
            f"{type(error).__name__}: the bank case list could not be read from "
            f"{base_url}. Nothing was written; start the mock and run again.",
            file=sys.stderr,
        )
        return 1

    destination = (
        case_meter_path
        if case_meter_path is not None
        else ROOT / "reports" / "meters.jsonl"
    )
    measured = measure_cases(
        plans,
        base_url,
        data_dir,
        meter_path=destination,
    )

    submissions: list[Contract] = [
        case["contract"] for case in measured if case["contract"] is not None
    ]
    _write_json(submission_path, submissions)
    evaluation = evaluate(dataset, gold, submissions)
    case_reports = build_case_reports(measured, evaluation)
    meters = meter_rows(case_reports)
    report = assemble_report(
        case_reports,
        evaluation,
        generated_at=generated_at,
        git_commit=git_commit,
        git_dirty=git_dirty,
        base_url=base_url,
        dataset_name=dataset["name"],
        meters=meters,
    )
    _write_json(report_path, report)
    _write_json(meters_path, meters)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(report, meters), encoding="utf-8")

    print(
        f"{report['pass_count']} / {report['total_cases']} cases passed; "
        f"{len(report['format_errors'])} format errors; "
        f"p95 {_fmt_ms(report['p95_latency_ms'])}; "
        f"cost per case {report['cost_per_case_usd']:.2f} USD"
    )
    for case in report["cases"]:
        if not case["passed"]:
            print(
                f"  {case['case_id']}: {', '.join(case['failed_checks'])}"
                + (f" ({case['error']})" if case["error"] else "")
            )
    return 0 if run_succeeded(report) else 1


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, run the scored run and return its exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8765",
        help="Base URL of the running mock (default: http://127.0.0.1:8765).",
    )
    parser.add_argument(
        "--data", type=Path, default=ROOT / "data" / "dev", help="Dataset directory."
    )
    parser.add_argument(
        "--gold",
        type=Path,
        default=ROOT / "feedback" / "dev_gold.json",
        help="Gold answers.",
    )
    parser.add_argument(
        "--submission",
        type=Path,
        default=ROOT / "submissions" / "scored-run.json",
        help="Where to write the evaluator submission array.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "reports" / "scored-run.json",
        help="Where to write the machine-readable report.",
    )
    parser.add_argument(
        "--meters",
        type=Path,
        default=ROOT / "reports" / "scored-run-meters.json",
        help="Where to write the meter rows.",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=ROOT / "reports" / "scored-run.md",
        help="Where to write the human-readable report.",
    )
    parser.add_argument(
        "--case-meters",
        type=Path,
        default=ROOT / "reports" / "meters.jsonl",
        help="Where the run writes its one redacted meter line per case.",
    )
    args = parser.parse_args(argv)
    commit, dirty = git_state(ROOT)
    return run_scored(
        base_url=args.base_url,
        data_dir=args.data,
        gold_path=args.gold,
        submission_path=args.submission,
        report_path=args.report,
        meters_path=args.meters,
        markdown_path=args.markdown,
        case_meter_path=args.case_meters,
        generated_at=utc_now(),
        git_commit=commit,
        git_dirty=dirty,
    )


if __name__ == "__main__":
    raise SystemExit(main())
