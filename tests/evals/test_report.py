"""The report must name failures, derive escalation outcomes and stay honest."""

from __future__ import annotations

from evals.contract import Check
from evals.report import (
    case_rows,
    escalation_summary,
    failing_lines,
    metric_rows,
    render_markdown,
    summarize,
)
from tests.evals.support import GOLD, make_case, make_run


def _route(case_id: str, actual: str, expected: str) -> tuple:
    gold = dict(GOLD, routing=[expected])
    contract = {
        "case_id": case_id,
        "classification": "unauthorized",
        "routing": actual,
        "citations": [],
        "narrative": "draft",
    }
    return make_case(case_id, gold=gold, contract=contract)


def test_metric_rows_carry_sample_size_and_rate():
    checks = [
        Check("escalation.route_correct", "CASE-1", True, "ok"),
        Check("escalation.route_correct", "CASE-2", False, "wrong"),
        Check("escalation.route_correct", "CASE-3", True, "ok"),
    ]
    rows = metric_rows(checks)
    assert rows[0]["n"] == 3
    assert rows[0]["passed"] == 2
    assert rows[0]["rate"] == 2 / 3
    assert "ci_low" not in rows[0]
    assert "ci_high" not in rows[0]


def test_case_rows_name_every_failing_check():
    run = make_run([make_case()])
    checks = [
        Check("escalation.route_correct", "CASE-1", True, "ok"),
        Check("tools.required_reads", "CASE-1", False, "merchant never answered 200"),
    ]
    rows = case_rows(run, checks)
    assert rows[0]["passed"] is False
    assert rows[0]["failures"][0]["metric"] == "tools.required_reads"
    assert "merchant" in rows[0]["failures"][0]["reason"]


def test_a_case_with_no_checks_is_a_failure_not_a_pass():
    rows = case_rows(make_run([make_case()]), [])
    assert rows[0]["passed"] is False
    assert rows[0]["failures"][0]["metric"] == "suite"


def test_escalation_summary_splits_normal_escalation_and_information():
    run = make_run(
        [
            _route("CASE-A", "ready_for_review", "ready_for_review"),
            _route("CASE-B", "manual_review", "ready_for_review"),
            _route("CASE-C", "request_information", "manual_review"),
            _route("CASE-D", "request_information", "request_information"),
        ]
    )
    summary = escalation_summary(run)
    assert summary["normal"] == {"total": 2, "passed": 1}
    assert summary["escalations"]["total"] == 1
    assert summary["escalations"]["passed"] == 0
    assert summary["escalations"]["missed"] == ["CASE-C"]
    assert summary["escalations"]["false"] == ["CASE-B"]
    assert summary["request_information"] == {"total": 1, "passed": 1}


def test_escalation_summary_excludes_unbuilt_cases_from_every_denominator():
    """A case that produced no draft was never routed, so it is not a miss."""
    built = _route("CASE-A", "ready_for_review", "ready_for_review")
    missing = make_case(
        "CASE-B",
        gold=dict(GOLD, routing=["manual_review"]),
        build_error="transactions never answered",
    )
    summary = escalation_summary(make_run([built, missing]))
    assert summary["normal"] == {"total": 1, "passed": 1}
    assert summary["escalations"]["total"] == 0
    assert summary["escalations"]["missed"] == []
    assert summary["not_built"] == ["CASE-B"]
    assert "Not built: CASE-B" in render_markdown(
        summarize(make_run([built, missing]), [], {})
    )


def test_failing_lines_name_each_failing_check_and_skip_passes():
    run = make_run([make_case()])
    checks = [
        Check("pii.restricted_values", "CASE-1", False, "a card number leaked"),
        Check("pii.synthetic_patterns", "CASE-1", True, "clean"),
    ]
    summary = summarize(run, checks, {})
    assert list(failing_lines(summary)) == [
        "CASE-1 pii.restricted_values: a card number leaked"
    ]


def test_markdown_lists_the_failing_case_and_metric():
    run = make_run([make_case()])
    checks = [Check("pii.restricted_values", "CASE-1", False, "a card number leaked")]
    summary = summarize(run, checks, {})
    text = render_markdown(summary)
    assert "CASE-1" in text
    assert "pii.restricted_values" in text
    assert "a card number leaked" in text
    assert "Cases fully passed: **0/1**" in text


def test_gates_fail_when_the_metric_is_missing():
    run = make_run([make_case()])
    summary = summarize(run, [Check("pii.patterns", "CASE-1", True, "ok")], {"tools": 0.9})
    assert summary["gates"][0]["passed"] is False
