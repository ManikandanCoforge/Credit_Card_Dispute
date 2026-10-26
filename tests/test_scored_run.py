"""Pure helpers behind the scored run. No live server is used.

The tests cover the nearest-rank p95, failed-check extraction, exception
mapping, meter row shape and report assembly, including a not-built case that
must be reported with its reason and submitted=false.
"""

import json
from pathlib import Path

import pytest

from tools.scored_run import (
    DETERMINISTIC_PATH,
    EXCEPTION_STATUS,
    assemble_report,
    build_case_reports,
    exception_list,
    failed_checks,
    measure_cases,
    meter_rows,
    p95_nearest_rank,
    proposed_exception,
    render_markdown,
    run_succeeded,
    unplanned_failures,
)

_PASSING = {1, 2, 3, 4, 8, 11, 12}
_FAILING = {5, 6, 7, 9, 10}
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("durations", "expected"),
    [
        ([], None),
        ([7.5], 7.5),
        ([1.0, 5.0], 5.0),
        ([5.0, 1.0], 5.0),
        ([3.0, 1.0, 2.0], 3.0),
        ([float(value) for value in range(1, 13)], 12.0),
        ([float(value) for value in range(1, 21)], 19.0),
        ([2.0, 2.0, 2.0], 2.0),
    ],
)
def test_p95_is_nearest_rank_over_the_measured_durations(durations, expected):
    assert p95_nearest_rank(durations) == expected


def test_p95_over_twelve_cases_is_the_slowest_case():
    assert p95_nearest_rank([10.0] * 11 + [99.0]) == 99.0


def test_failed_checks_are_the_sorted_false_names():
    checks = {"routing": True, "facts": False, "citations_valid": False}
    assert failed_checks(checks) == ["citations_valid", "facts"]


def test_failed_checks_is_empty_when_everything_passed():
    assert failed_checks({"routing": True, "facts": True}) == []


def test_a_not_submitted_case_fails_only_the_submitted_check():
    assert failed_checks({"submitted": False}) == ["submitted"]


@pytest.mark.parametrize(
    ("case_id", "ticket"),
    [
        ("CARD-D05", "COF-39"),
        ("CARD-D06", "COF-39"),
        ("CARD-D07", "COF-40"),
        ("CARD-D09", "COF-43"),
        ("CARD-D10", "COF-40"),
    ],
)
def test_each_failing_dev_case_maps_to_a_proposed_ticket(case_id, ticket):
    mapping = proposed_exception(case_id)
    assert mapping is not None
    assert mapping[0] == ticket
    assert mapping[1]


def test_a_passing_case_has_no_proposed_ticket():
    assert proposed_exception("CARD-D01") is None


def test_another_failure_of_a_mapped_case_is_not_excused():
    assert proposed_exception("CARD-D05", ["submitted"]) is not None
    assert proposed_exception("CARD-D05", ["transaction_facts"]) is None


def test_exception_entries_are_explicitly_pending_pod_agreement():
    reports = [
        _case(
            "CARD-D05",
            submitted=False,
            passed=False,
            failed=["submitted"],
            error="the case names evidence this step cannot read: CARD-D05-FOLLOWUP",
        )
    ]

    entries = exception_list(reports)

    assert len(entries) == 1
    entry = entries[0]
    assert entry["case_id"] == "CARD-D05"
    assert entry["ticket"] == "COF-39"
    assert entry["status"] == "proposed_pending_pod_agreement"
    assert entry["failed_checks"] == ["submitted"]
    assert entry["error"].startswith("the case names evidence")
    assert entry["note"]


def test_exception_list_skips_passing_cases():
    assert exception_list([_case("CARD-D01", passed=True)]) == []


def test_an_unmapped_failure_is_not_excused():
    reports = [_case("CARD-D99", passed=False, failed=["routing"], error=None)]

    assert exception_list(reports) == []
    assert unplanned_failures(reports) == [
        {"case_id": "CARD-D99", "failed_checks": ["routing"], "error": None}
    ]


def test_meter_rows_are_one_measured_deterministic_row_per_case():
    reports = [
        _case("CARD-D01", duration=1.234),
        _case("CARD-D02", duration=2.5),
    ]

    rows = meter_rows(reports)

    assert [row["case_id"] for row in rows] == ["CARD-D01", "CARD-D02"]
    assert rows[0] == {
        "case_id": "CARD-D01",
        "duration_ms": 1.234,
        "model_calls": 0,
        "model_tokens_in": 0,
        "model_tokens_out": 0,
        "cost_usd": 0.0,
        "path": DETERMINISTIC_PATH,
    }
    assert all(row["path"] == "deterministic_template" for row in rows)
    assert all(row["cost_usd"] == 0.0 for row in rows)


def test_a_not_built_case_is_reported_with_its_reason_and_submitted_false():
    measured = [
        {
            "case_id": "CARD-D05",
            "duration_ms": 1.5,
            "contract": None,
            "error": (
                "the case names evidence this step cannot read: CARD-D05-FOLLOWUP"
            ),
        }
    ]
    evaluation = _evaluation(
        [{"case_id": "CARD-D05", "passed": False, "checks": {"submitted": False}}]
    )

    assert build_case_reports(measured, evaluation) == [
        {
            "case_id": "CARD-D05",
            "submitted": False,
            "passed": False,
            "duration_ms": 1.5,
            "failed_checks": ["submitted"],
            "error": (
                "the case names evidence this step cannot read: CARD-D05-FOLLOWUP"
            ),
        }
    ]


def test_a_built_case_carries_every_failed_check_from_the_evaluator():
    measured = [
        {
            "case_id": "CARD-D06",
            "duration_ms": 2.0,
            "contract": {"case_id": "CARD-D06"},
            "error": None,
        }
    ]
    evaluation = _evaluation(
        [
            {
                "case_id": "CARD-D06",
                "passed": False,
                "checks": {
                    "classification": False,
                    "routing": False,
                    "citations_valid": True,
                },
            }
        ]
    )

    report = build_case_reports(measured, evaluation)[0]

    assert report["submitted"] is True
    assert report["failed_checks"] == ["classification", "routing"]


def test_a_case_the_evaluator_never_mentions_is_not_a_pass():
    measured = [
        {
            "case_id": "CARD-DXX",
            "duration_ms": 0.5,
            "contract": {"case_id": "CARD-DXX"},
            "error": None,
        }
    ]

    report = build_case_reports(measured, _evaluation([]))[0]

    assert report["passed"] is False
    assert report["failed_checks"] == ["missing_from_evaluation"]


def test_assemble_report_carries_counts_p95_and_measured_zero_cost():
    reports = [
        _case("CARD-D01", passed=True, duration=1.0),
        _case(
            "CARD-D05",
            submitted=False,
            passed=False,
            duration=3.0,
            failed=["submitted"],
            error="follow-up unread",
        ),
    ]

    report = assemble_report(
        reports,
        _evaluation([]),
        generated_at="2026-10-25T00:00:00Z",
        git_commit="abc123",
        git_dirty=True,
        base_url="http://127.0.0.1:8899",
        dataset_name="card-disputes-dev",
    )

    assert report["pass_count"] == 1
    assert report["total_cases"] == 2
    assert report["format_errors"] == []
    assert report["p95_latency_ms"] == 3.0
    assert report["cost_per_case_usd"] == 0.0
    assert report["total_cost_usd"] == 0.0
    assert report["cases"] == reports
    assert report["exceptions"][0]["case_id"] == "CARD-D05"
    assert report["exception_status"] == EXCEPTION_STATUS
    assert report["generated_at"] == "2026-10-25T00:00:00Z"
    assert "0 model calls" in report["cost_note"]


@pytest.mark.parametrize(
    ("pass_count", "total_cases", "format_errors", "expected"),
    [
        (12, 12, [], True),
        (12, 12, ["Unexpected case: X"], False),
        (11, 12, [], False),
        (0, 12, [], False),
        (7, 7, [], True),
        (0, 0, [], False),
    ],
)
def test_exit_is_success_only_when_every_case_passes(
    pass_count, total_cases, format_errors, expected
):
    report = {
        "pass_count": pass_count,
        "total_cases": total_cases,
        "format_errors": format_errors,
    }
    assert run_succeeded(report) is expected


def test_markdown_states_the_pass_count_and_format_errors():
    markdown = render_markdown(_twelve_case_report(), meter_rows(_twelve_cases()))
    assert "Pass: 7 / 12" in markdown
    assert "Format errors: 0" in markdown


def test_markdown_names_every_failing_case_and_its_exact_check():
    markdown = render_markdown(_twelve_case_report(), meter_rows(_twelve_cases()))
    for number in sorted(_FAILING):
        assert f"CARD-D{number:02d}" in markdown
    assert "submitted" in markdown


def test_markdown_marks_the_exceptions_as_proposed_not_agreed():
    markdown = render_markdown(_twelve_case_report(), meter_rows(_twelve_cases()))
    lowered = markdown.lower()
    assert "proposed, pending pod agreement" in lowered
    assert "not agreed scope" in lowered


def test_markdown_reports_p95_and_cost_from_the_meter_file():
    markdown = render_markdown(_twelve_case_report(), meter_rows(_twelve_cases()))
    assert "p95 draft latency" in markdown
    assert "Cost per case: 0.00 USD" in markdown
    assert "reports/scored-run-meters.json" in markdown


def test_markdown_contains_the_exact_reproduction_commands():
    markdown = render_markdown(_twelve_case_report(), meter_rows(_twelve_cases()))
    assert "rm -f .state/cof44.sqlite3" in markdown
    assert "tools.runtime serve" in markdown
    assert "--port 8899" in markdown
    assert "tools/scored_run.py" in markdown
    assert "--gold feedback/dev_gold.json" in markdown


def _case(
    case_id,
    *,
    submitted=True,
    passed=True,
    duration=1.0,
    failed=None,
    error=None,
):
    return {
        "case_id": case_id,
        "submitted": submitted,
        "passed": passed,
        "duration_ms": duration,
        "failed_checks": [] if failed is None else list(failed),
        "error": error,
    }


def _evaluation(cases):
    return {
        "passed": False,
        "format_errors": [],
        "cases": cases,
        "passed_cases": sum(1 for case in cases if case["passed"]),
        "total_cases": len(cases),
    }


def _twelve_cases():
    cases = []
    for number in range(1, 13):
        case_id = f"CARD-D{number:02d}"
        if number in _PASSING:
            cases.append(_case(case_id, duration=float(number)))
        else:
            cases.append(
                _case(
                    case_id,
                    submitted=False,
                    passed=False,
                    duration=float(number),
                    failed=["submitted"],
                    error=f"{case_id} was not built",
                )
            )
    return cases


def _twelve_case_report():
    return assemble_report(
        _twelve_cases(),
        _evaluation([]),
        generated_at="2026-10-25T00:00:00Z",
        git_commit="abc123",
        git_dirty=True,
        base_url="http://127.0.0.1:8899",
        dataset_name="card-disputes-dev",
    )


def test_report_cost_is_read_from_the_supplied_meter_rows():
    reports = [
        _case("CARD-D01", passed=True, duration=1.0),
        _case("CARD-D02", passed=True, duration=2.0),
    ]
    meters = [
        {
            "case_id": "CARD-D01",
            "duration_ms": 1.0,
            "model_calls": 1,
            "model_tokens_in": 10,
            "model_tokens_out": 5,
            "cost_usd": 0.30,
            "path": "model_prose",
        },
        {
            "case_id": "CARD-D02",
            "duration_ms": 2.0,
            "model_calls": 1,
            "model_tokens_in": 10,
            "model_tokens_out": 5,
            "cost_usd": 0.10,
            "path": "model_prose",
        },
    ]

    report = assemble_report(
        reports,
        _evaluation([]),
        generated_at="2026-10-25T00:00:00Z",
        git_commit="abc123",
        git_dirty=False,
        base_url="http://127.0.0.1:8899",
        dataset_name="card-disputes-dev",
        meters=meters,
    )

    assert report["total_cost_usd"] == 0.4
    assert report["cost_per_case_usd"] == 0.2


def test_the_git_commit_note_tracks_the_dirty_flag():
    common = {
        "evaluation": _evaluation([]),
        "generated_at": "2026-10-25T00:00:00Z",
        "git_commit": "abc123",
        "base_url": "http://127.0.0.1:8899",
        "dataset_name": "card-disputes-dev",
    }

    clean = assemble_report([_case("CARD-D01")], git_dirty=False, **common)
    dirty = assemble_report([_case("CARD-D01")], git_dirty=True, **common)

    assert "working tree was clean" in clean["git_commit_note"]
    assert "uncommitted changes" in dirty["git_commit_note"]


def test_measure_cases_times_the_injected_builder(tmp_path):
    plans = [{"record": {"case_id": "CARD-D01"}, "documents": []}]
    seen = []

    def build(plan):
        seen.append(plan["record"]["case_id"])
        return {"case_id": "CARD-D01", "contract": None, "error": "stop"}

    measured = measure_cases(plans, "http://127.0.0.1:8899", tmp_path, build=build)

    assert seen == ["CARD-D01"]
    assert measured == [
        {
            "case_id": "CARD-D01",
            "duration_ms": measured[0]["duration_ms"],
            "contract": None,
            "error": "stop",
        }
    ]
    assert measured[0]["duration_ms"] >= 0.0


def test_the_committed_report_matches_its_meters_and_markdown():
    report = json.loads((ROOT / "reports" / "scored-run.json").read_text())
    meters = json.loads((ROOT / "reports" / "scored-run-meters.json").read_text())
    markdown = (ROOT / "reports" / "scored-run.md").read_text()

    assert report["total_cases"] == len(meters) == 12
    assert report["pass_count"] == sum(1 for case in report["cases"] if case["passed"])
    assert report["p95_latency_ms"] == p95_nearest_rank(
        [row["duration_ms"] for row in meters]
    )
    assert report["total_cost_usd"] == round(
        sum(row["cost_usd"] for row in meters), 6
    )
    assert report["exception_status"] == EXCEPTION_STATUS
    assert markdown == render_markdown(report, meters)
