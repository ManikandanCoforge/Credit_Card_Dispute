"""The committed scored run is the only source of the numbers the docs quote.

README, the demo rehearsal numbers lock and the readable report all describe the
same run, the one reports/scored-run.json records. This test reads that artifact
and fails when a hand edit leaves a doc behind, naming the file, the number the
doc states and the number the report holds.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "scored-run.json"
README = ROOT / "README.md"
REHEARSAL = ROOT / "docs" / "DEMO_REHEARSAL.md"
REPORT_MD = ROOT / "reports" / "scored-run.md"


def _report():
    return json.loads(REPORT.read_text(encoding="utf-8"))


def _text(path):
    return path.read_text(encoding="utf-8")


def _name(path):
    return path.relative_to(ROOT).as_posix()


def _expect(condition, path, label, found, expected):
    assert condition, (
        f"{_name(path)} says {found!r} for {label}; "
        f"reports/scored-run.json holds {expected!r}"
    )


def _readme_paragraph():
    text = _text(README)
    start = text.index("Measured on")
    end = text.find("\n\n", start)
    return text[start:] if end == -1 else text[start:end]


def _latency(text, path, label, pattern, value):
    match = re.search(pattern, text)
    assert match, f"{_name(path)} does not state {label}"
    found = match.group(1)
    accepted = {str(int(value)), f"{value:.3f}"}
    _expect(
        float(found) == float(value) and found in accepted,
        path,
        label,
        found,
        value,
    )


def _lock_row(text, name):
    for line in text.splitlines():
        if line.startswith(f"| {name} |"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            return cells[2]
    raise AssertionError(f"docs/DEMO_REHEARSAL.md has no numbers lock row {name!r}")


def _sha(text, length):
    match = re.search(rf"\b[0-9a-f]{{{length}}}\b", text)
    return match.group(0) if match else f"no {length}-character commit sha"


def test_the_report_is_from_a_clean_full_commit():
    report = _report()
    commit = report["git_commit"]
    assert re.fullmatch(r"[0-9a-f]{40}", commit), (
        f"reports/scored-run.json holds git_commit {commit!r}, "
        "not a full lowercase commit sha"
    )
    assert report["git_dirty"] is False
    assert report["total_cases"] == 12


def test_readme_quotes_the_report():
    report = _report()
    text = _readme_paragraph()
    short = report["git_commit"][:7]

    match = re.search(r"(\d+) of (\d+) passed", text)
    assert match, "README.md does not state 'N of 12 passed'"
    found = match.group(1) + " of " + match.group(2)
    expected = f"{report['pass_count']} of {report['total_cases']}"
    _expect(found == expected, README, "cases passed", found, expected)

    match = re.search(r"(\d+) format errors", text)
    assert match, "README.md does not state 'N format errors'"
    expected = str(len(report["format_errors"]))
    _expect(match.group(1) == expected, README, "format errors", match.group(1), expected)

    _latency(text, README, "p50", r"p50 (\d+(?:\.\d+)?) ms", report["p50_latency_ms"])
    _latency(text, README, "p95", r"p95 (\d+(?:\.\d+)?) ms", report["p95_latency_ms"])

    _expect(short in text, README, "the short commit", _sha(text, 7), short)


def test_the_rehearsal_numbers_lock_quotes_the_report():
    report = _report()
    text = _text(REHEARSAL)
    short = report["git_commit"][:7]

    passed = _lock_row(text, "Cases passed")
    expected = f"{report['pass_count']} of {report['total_cases']}"
    _expect(passed == expected, REHEARSAL, "cases passed", passed, expected)

    errors = _lock_row(text, "Format errors")
    expected = str(len(report["format_errors"]))
    _expect(errors == expected, REHEARSAL, "format errors", errors, expected)

    lock_p50 = _lock_row(text, "p50 draft latency")
    _latency(lock_p50, REHEARSAL, "p50", r"^(\d+(?:\.\d+)?) ms", report["p50_latency_ms"])
    lock_p95 = _lock_row(text, "p95 draft latency")
    _latency(lock_p95, REHEARSAL, "p95", r"^(\d+(?:\.\d+)?) ms", report["p95_latency_ms"])

    failing = ", ".join(
        case["case_id"] for case in report["cases"] if not case["passed"]
    )
    cases = _lock_row(text, "Failing cases")
    if failing:
        expected = f"{failing} only"
        _expect(cases == expected, REHEARSAL, "failing cases", cases, expected)
    else:
        _expect(cases == "None", REHEARSAL, "failing cases", cases, "None")

    cost = _lock_row(text, "Cost per case")
    expected = f"{report['cost_per_case_usd']:.2f} USD, 0 model calls, 0 tokens"
    _expect(cost == expected, REHEARSAL, "cost per case", cost, expected)

    _expect(short in text, REHEARSAL, "the short commit", _sha(text, 7), short)
    _expect(
        report["git_commit"] in text,
        REHEARSAL,
        "the full commit",
        _sha(text, 40),
        report["git_commit"],
    )


def test_the_readable_report_quotes_the_json_report():
    report = _report()
    text = _text(REPORT_MD)

    match = re.search(r"- Pass: (\d+) / (\d+)", text)
    assert match, "reports/scored-run.md does not state '- Pass: N / 12'"
    expected = f"{report['pass_count']} of {report['total_cases']}"
    _expect(
        match.group(1) + " of " + match.group(2) == expected,
        REPORT_MD,
        "cases passed",
        match.group(0),
        expected,
    )

    match = re.search(r"- Format errors: (\d+)", text)
    assert match, "reports/scored-run.md does not state '- Format errors: N'"
    expected = str(len(report["format_errors"]))
    _expect(match.group(1) == expected, REPORT_MD, "format errors", match.group(1), expected)

    _latency(
        text,
        REPORT_MD,
        "p50",
        r"p50 draft latency: (\d+(?:\.\d+)?) ms",
        report["p50_latency_ms"],
    )
    _latency(
        text,
        REPORT_MD,
        "p95",
        r"p95 draft latency: (\d+(?:\.\d+)?) ms",
        report["p95_latency_ms"],
    )

    _expect(
        report["git_commit"] in text,
        REPORT_MD,
        "the full commit",
        _sha(text, 40),
        report["git_commit"],
    )
    _expect(
        report["generated_at"] in text,
        REPORT_MD,
        "the timestamp",
        report["generated_at"],
        report["generated_at"],
    )
