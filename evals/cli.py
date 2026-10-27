"""The command surface: run one suite and write the two reports."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from evals.dataset import REPO_ROOT, SuiteError, load_suite
from evals.metrics import run_metrics
from evals.report import failing_lines, summarize, write_json, write_markdown
from evals.runner import run_evaluation


def main(argv: Sequence[str] | None = None) -> int:
    """Parse one suite run, execute it and return the process exit code."""
    parser = argparse.ArgumentParser(
        prog="python -m evals",
        description="Run the offline evaluation suite over one dataset.",
    )
    parser.add_argument(
        "--suite",
        default=str(REPO_ROOT / "evals" / "suites" / "dev.json"),
        help="suite file, relative to the repository root",
    )
    parser.add_argument("--data", help="override the dataset directory")
    parser.add_argument("--gold", help="override the gold file")
    parser.add_argument("--name", help="override the set name used in the report")
    parser.add_argument("--out", help="report base path, without extension")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="write the reports but exit 0 even when checks fail",
    )
    arguments = parser.parse_args(list(argv) if argv is not None else None)
    try:
        suite = load_suite(Path(arguments.suite))
        data_dir = Path(arguments.data) if arguments.data else suite["data"]
        gold_path = Path(arguments.gold) if arguments.gold else suite["gold"]
        name = arguments.name or suite["name"]
        run = run_evaluation(data_dir, gold_path, name)
        checks = run_metrics(run, suite["metrics"] or None)
    except SuiteError as error:
        print(f"eval: {error}", file=sys.stderr)
        return 2
    summary = summarize(run, checks, suite["gates"])
    base = Path(arguments.out) if arguments.out else REPO_ROOT / "reports" / f"eval-{name}"
    write_json(base.with_suffix(".json"), summary, checks)
    write_markdown(base.with_suffix(".md"), summary)
    _print_summary(summary, base)
    failed = any(not row["passed"] for row in summary["case_results"])
    gates_failed = any(not gate["passed"] for gate in summary["gates"])
    if arguments.report_only:
        return 0
    return 1 if failed or gates_failed or summary["format_errors"] else 0


def _print_summary(summary: dict[str, Any], base: Path) -> None:
    """Print the pass count, each metric rate and every failing check."""
    cases = summary["cases"]
    if not isinstance(cases, dict):
        raise TypeError("summary is missing its case totals")
    print(
        f"{summary['suite']}: {cases['passed']}/{cases['total']} cases fully passed, "
        f"{len(summary['format_errors'])} format error(s)"
    )
    for row in summary["metrics"]:
        low = "n/a" if row["ci_low"] is None else f"{row['ci_low'] * 100:.1f}%"
        high = "n/a" if row["ci_high"] is None else f"{row['ci_high'] * 100:.1f}%"
        rate = "n/a" if row["rate"] is None else f"{row['rate'] * 100:.1f}%"
        print(
            f"  {row['metric']:<28} {row['passed']}/{row['n']}  {rate}  [{low}, {high}]"
        )
    for line in failing_lines(summary):
        print(f"  FAIL {line}")
    print(f"wrote {base.with_suffix('.json')}")
    print(f"wrote {base.with_suffix('.md')}")
