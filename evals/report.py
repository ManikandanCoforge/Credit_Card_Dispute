"""Turn checks into the JSON artifact and the Markdown report.

The report is deliberately blunt: every metric carries its sample size and a
95 percent interval, every failing check is listed under its case, and a case
with no checks is reported as a suite defect rather than a pass.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from evals.contract import Check, RunData
from evals.dataset import REPO_ROOT
from evals.stats import proportion, wilson_interval


def metric_rows(checks: Sequence[Check]) -> list[dict[str, Any]]:
    """Aggregate checks by metric key, in first-seen order."""
    grouped: dict[str, list[Check]] = {}
    for check in checks:
        grouped.setdefault(check.metric, []).append(check)
    rows: list[dict[str, Any]] = []
    for metric, items in grouped.items():
        passed = sum(1 for item in items if item.passed)
        rate = proportion(passed, len(items))
        low, high = wilson_interval(passed, len(items))
        rows.append(
            {
                "metric": metric,
                "n": len(items),
                "passed": passed,
                "rate": rate,
                "ci_low": low,
                "ci_high": high,
            }
        )
    return rows


def case_rows(run: RunData, checks: Sequence[Check]) -> list[dict[str, Any]]:
    """One row per case, with every failing check named individually."""
    grouped: dict[str, list[Check]] = defaultdict(list)
    for check in checks:
        grouped[check.case_id].append(check)
    rows: list[dict[str, Any]] = []
    for case in run.cases:
        items = grouped.get(case.case_id, [])
        failures = [
            {
                "metric": item.metric,
                "reason": item.reason,
                "evidence": dict(item.evidence),
            }
            for item in items
            if not item.passed
        ]
        if not items:
            failures.append(
                {
                    "metric": "suite",
                    "reason": "no checks ran for this case",
                    "evidence": {},
                }
            )
        rows.append(
            {
                "case_id": case.case_id,
                "passed": not failures,
                "build_error": case.build_error,
                "routing": (case.contract or {}).get("routing"),
                "expected_routing": list(case.gold.get("routing", [])),
                "failures": failures,
            }
        )
    return rows


def escalation_summary(run: RunData) -> dict[str, Any]:
    """Derive normal, escalation and request-information outcomes from gold."""
    normal: dict[str, Any] = {"total": 0, "passed": 0}
    escalations: dict[str, Any] = {
        "total": 0,
        "passed": 0,
        "missed": [],
        "false": [],
    }
    information: dict[str, Any] = {"total": 0, "passed": 0}
    for case in run.cases:
        expected = list(case.gold.get("routing", []))
        actual = (case.contract or {}).get("routing")
        if expected == ["ready_for_review"]:
            normal["total"] += 1
            if actual == "ready_for_review":
                normal["passed"] += 1
            if actual == "manual_review":
                escalations["false"].append(case.case_id)
        elif expected == ["manual_review"]:
            escalations["total"] += 1
            if actual == "manual_review":
                escalations["passed"] += 1
            else:
                escalations["missed"].append(case.case_id)
        elif expected == ["request_information"]:
            information["total"] += 1
            if actual == "request_information":
                information["passed"] += 1
    return {
        "normal": normal,
        "escalations": escalations,
        "request_information": information,
    }


def summarize(
    run: RunData, checks: Sequence[Check], gates: Mapping[str, float]
) -> dict[str, Any]:
    """Build the whole report payload: cases, metrics, gates and escalation."""
    cases = case_rows(run, checks)
    metrics = metric_rows(checks)
    by_key = {row["metric"]: row for row in metrics}
    gate_rows = []
    for metric, minimum in gates.items():
        row = by_key.get(metric)
        rate = row["rate"] if row else None
        gate_rows.append(
            {
                "metric": metric,
                "minimum": minimum,
                "rate": rate,
                "passed": rate is not None and rate >= minimum,
            }
        )
    return {
        "suite": run.set_name,
        "commit": run.commit,
        "started_at": run.started_at,
        "data_dir": _display(run.data_dir),
        "gold_path": _display(run.gold_path),
        "cases": {
            "total": len(cases),
            "passed": sum(1 for row in cases if row["passed"]),
        },
        "format_errors": list(run.format_errors),
        "metrics": metrics,
        "gates": gate_rows,
        "escalation": escalation_summary(run),
        "case_results": cases,
    }


def write_json(path: Path, summary: Mapping[str, Any], checks: Sequence[Check]) -> None:
    """Write the machine-readable artifact, including every check's evidence."""
    payload = dict(summary)
    payload["checks"] = [
        {
            "metric": check.metric,
            "case_id": check.case_id,
            "passed": check.passed,
            "reason": check.reason,
            "evidence": dict(check.evidence),
        }
        for check in checks
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def render_markdown(summary: Mapping[str, Any]) -> str:
    """Render the human-readable report from the same payload as the JSON."""
    cases = summary["cases"]
    lines = [
        f"# Evaluation report - {summary['suite']}",
        "",
        f"- Commit: `{summary['commit']}`",
        f"- Data: `{summary['data_dir']}`",
        f"- Gold: `{summary['gold_path']}`",
        f"- Generated: {summary['started_at']}",
        f"- Cases fully passed: **{cases['passed']}/{cases['total']}**",
        f"- Format errors: {len(summary['format_errors'])}",
        "",
        "## Metrics",
        "",
        "| Metric | Passed | n | Rate | 95% CI |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in summary["metrics"]:
        interval = f"{_percent(row['ci_low'])} - {_percent(row['ci_high'])}"
        lines.append(f"| `{row['metric']}` | {row['passed']} | {row['n']} | {_percent(row['rate'])} | {interval} |")
    if summary["gates"]:
        lines += ["", "## Gates", ""]
        for gate in summary["gates"]:
            state = "pass" if gate["passed"] else "FAIL"
            lines.append(
                f"- `{gate['metric']}` >= {_percent(gate['minimum'])}: {state} "
                f"(observed {_percent(gate['rate'])})"
            )
    escalation = summary["escalation"]
    lines += [
        "",
        "## Escalation",
        "",
        f"- Normal cases routed normally: {escalation['normal']['passed']}/{escalation['normal']['total']}",
        f"- Correct escalations: {escalation['escalations']['passed']}/{escalation['escalations']['total']}",
        f"- Missed escalations: {_names(escalation['escalations']['missed'])}",
        f"- False escalations: {_names(escalation['escalations']['false'])}",
        f"- Request-information routes: {escalation['request_information']['passed']}/{escalation['request_information']['total']}",
    ]
    if summary["format_errors"]:
        lines += ["", "## Format errors", ""]
        lines += [f"- {error}" for error in summary["format_errors"]]
    failing = [row for row in summary["case_results"] if not row["passed"]]
    lines += ["", "## Failures", ""]
    if not failing:
        lines.append("No failing cases in this run.")
    for row in failing:
        heading = f"### {row['case_id']}"
        if row["build_error"]:
            heading += f" - not built: {row['build_error']}"
        lines += [heading, ""]
        for failure in row["failures"]:
            lines.append(f"- `{failure['metric']}` - {failure['reason']}")
        lines.append("")
    lines += [
        "## Limits",
        "",
        "- Deterministic checks only. Semantic grounding, prose safety and the observed demo remain human review.",
        "- The hidden set is scored only when its data and gold are injected; this report never claims a hidden result it did not run.",
        "- A passing report does not by itself award rubric points.",
        "",
    ]
    return "\n".join(lines)


def write_markdown(path: Path, summary: Mapping[str, Any]) -> None:
    """Write the Markdown report next to the JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(summary), encoding="utf-8")


def failing_lines(summary: Mapping[str, Any]) -> Iterable[str]:
    """Yield one line per failing check, for the terminal summary."""
    for row in summary["case_results"]:
        for failure in row["failures"]:
            yield f"{row['case_id']} {failure['metric']}: {failure['reason']}"


def _percent(value: float | None) -> str:
    """Format a rate as a percentage with one decimal, or `n/a`."""
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _display(path: Path) -> str:
    """Show a path relative to the repository root when it lives inside it."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _names(values: Sequence[str]) -> str:
    """Render a short list of case ids, or `none`."""
    return ", ".join(values) if values else "none"
