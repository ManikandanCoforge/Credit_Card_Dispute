"""The tool-call metric must judge the audit, never the dataset's intent.

Every test overrides one fixture field, so a failure names the audit fact it is
about rather than the fixture. The dataset fixture declares both tools; a test
that narrows the case tools proves the dataset is not consulted.
"""

from __future__ import annotations

from typing import Any

import pytest

from evals.contract import CaseOutcome, Check
from evals.metrics import tools
from tests.evals.support import make_case, make_run, tool_event, write_event

REQUIRED_READS = "tools.required_reads"
NO_FORBIDDEN_WRITES = "tools.no_forbidden_writes"
RETRY_BOUND = "tools.retry_bound"
NO_EXTRA_READS = "tools.no_extra_reads"

CHECK_ORDER = (
    REQUIRED_READS,
    NO_FORBIDDEN_WRITES,
    RETRY_BOUND,
    NO_EXTRA_READS,
)

CASE = "CASE-1"


def checks(outcome: CaseOutcome) -> dict[str, Check]:
    """Run the metric over one case and index the four checks it must emit."""
    assert tools.NAME == "tools"
    result = tools.run(make_run([outcome]))
    assert [check.metric for check in result] == list(CHECK_ORDER)
    assert all(check.case_id == outcome.case_id for check in result)
    return {check.metric: check for check in result}


def clean_audit(case_id: str = CASE) -> list[dict[str, Any]]:
    """Return the rows of a case that read both declared tools once each."""
    return [
        tool_event(case_id, "transactions", 1, 200),
        tool_event(case_id, "merchant", 1, 200),
    ]


def test_clean_two_tool_case_passes_all_four() -> None:
    result = checks(make_case(audit=clean_audit()))
    assert [name for name in result if not result[name].passed] == []
    assert result[REQUIRED_READS].evidence["declared_tools"] == ["transactions", "merchant"]
    assert result[REQUIRED_READS].evidence["attempts"] == {
        "transactions": [200],
        "merchant": [200],
    }
    assert result[REQUIRED_READS].evidence["missing"] == []
    assert result[NO_FORBIDDEN_WRITES].evidence["offending"] == []
    assert result[RETRY_BOUND].evidence["limit"] == 3
    assert result[NO_EXTRA_READS].evidence["extra_tools"] == []


def test_missing_merchant_read_fails_required_reads() -> None:
    result = checks(make_case(audit=[tool_event(CASE, "transactions", 1, 200)]))
    assert not result[REQUIRED_READS].passed
    assert result[REQUIRED_READS].evidence["missing"] == ["merchant"]
    assert "merchant" in result[REQUIRED_READS].reason
    assert result[NO_FORBIDDEN_WRITES].passed
    assert result[RETRY_BOUND].passed
    assert result[NO_EXTRA_READS].passed


def test_tool_with_only_503s_fails_required_reads_and_says_so() -> None:
    result = checks(
        make_case(
            audit=[
                tool_event(CASE, "transactions", 1, 200),
                tool_event(CASE, "merchant", 1, 503),
                tool_event(CASE, "merchant", 2, 503),
            ]
        )
    )
    assert not result[REQUIRED_READS].passed
    assert result[REQUIRED_READS].evidence["missing"] == ["merchant"]
    assert result[REQUIRED_READS].evidence["attempts"]["merchant"] == [503, 503]
    assert "merchant" in result[REQUIRED_READS].reason
    assert "503" in result[REQUIRED_READS].reason
    assert result[RETRY_BOUND].passed
    assert result[NO_EXTRA_READS].passed


def test_transient_503_then_200_satisfies_required_reads() -> None:
    result = checks(
        make_case(
            audit=[
                tool_event(CASE, "transactions", 1, 503),
                tool_event(CASE, "transactions", 2, 200),
                tool_event(CASE, "merchant", 1, 200),
            ]
        )
    )
    assert result[REQUIRED_READS].passed
    assert result[RETRY_BOUND].passed


def test_four_attempts_on_one_tool_fails_retry_bound() -> None:
    result = checks(
        make_case(
            audit=[
                tool_event(CASE, "transactions", 1, 200),
                tool_event(CASE, "merchant", 1, 503),
                tool_event(CASE, "merchant", 2, 503),
                tool_event(CASE, "merchant", 3, 503),
                tool_event(CASE, "merchant", 4, 200),
            ]
        )
    )
    assert not result[RETRY_BOUND].passed
    assert result[RETRY_BOUND].evidence["over_limit"] == {"merchant": 4}
    assert "merchant" in result[RETRY_BOUND].reason
    assert result[REQUIRED_READS].passed
    assert result[NO_FORBIDDEN_WRITES].passed
    assert result[NO_EXTRA_READS].passed


def test_three_attempts_stay_within_the_retry_bound() -> None:
    result = checks(
        make_case(
            audit=[
                tool_event(CASE, "transactions", 1, 200),
                tool_event(CASE, "merchant", 1, 503),
                tool_event(CASE, "merchant", 2, 503),
                tool_event(CASE, "merchant", 3, 200),
            ]
        )
    )
    assert result[RETRY_BOUND].passed
    assert result[RETRY_BOUND].evidence["over_limit"] == {}
    assert result[REQUIRED_READS].passed


def test_the_pass_reason_names_how_each_tool_answered() -> None:
    """A pass must not claim 200 for a tool that used its retry budget."""
    result = checks(make_case(audit=clean_audit()))
    assert (
        result[REQUIRED_READS].reason
        == "transactions answered 200; merchant answered 200"
    )


def test_the_pass_reason_names_a_retry_budget() -> None:
    """A persistent outage that exhausted the budget is reported as such."""
    result = checks(
        make_case(
            audit=[
                tool_event(CASE, "transactions", 1, 503),
                tool_event(CASE, "transactions", 2, 503),
                tool_event(CASE, "transactions", 3, 503),
                tool_event(CASE, "merchant", 1, 200),
            ]
        )
    )
    assert result[REQUIRED_READS].passed is True
    assert result[REQUIRED_READS].reason == (
        "transactions used its retry budget (503, 503, 503); merchant answered 200"
    )


def test_the_pass_reason_names_the_attempt_that_answered() -> None:
    """A retried read says which attempt answered."""
    result = checks(
        make_case(
            audit=[
                tool_event(CASE, "transactions", 1, 503),
                tool_event(CASE, "transactions", 2, 200),
                tool_event(CASE, "merchant", 1, 200),
            ]
        )
    )
    assert "transactions answered 200 on attempt 2" in result[REQUIRED_READS].reason


def test_three_retryable_failures_are_a_correct_outage() -> None:
    """A tool that used the whole retry budget on 503s is not a missing read."""
    result = checks(
        make_case(
            audit=[
                tool_event(CASE, "transactions", 1, 503),
                tool_event(CASE, "transactions", 2, 503),
                tool_event(CASE, "transactions", 3, 503),
                tool_event(CASE, "merchant", 1, 200),
            ]
        )
    )
    assert result[REQUIRED_READS].passed
    assert result[REQUIRED_READS].evidence["missing"] == []
    assert result[RETRY_BOUND].passed


def test_one_503_without_a_retry_fails_with_the_missing_retry() -> None:
    """Giving up after one transient failure is the defect, not the outage."""
    result = checks(
        make_case(
            audit=[
                tool_event(CASE, "transactions", 1, 200),
                tool_event(CASE, "merchant", 1, 503),
            ]
        )
    )
    assert result[REQUIRED_READS].passed is False
    assert result[REQUIRED_READS].reason == "merchant answered 503 and was not retried"


def test_two_503s_without_a_third_attempt_do_not_exhaust_the_budget() -> None:
    """Two attempts leave a retry unused, so the outage was not handled."""
    result = checks(
        make_case(
            audit=[
                tool_event(CASE, "transactions", 1, 200),
                tool_event(CASE, "merchant", 1, 503),
                tool_event(CASE, "merchant", 2, 503),
            ]
        )
    )
    assert result[REQUIRED_READS].passed is False
    assert "was not retried" in result[REQUIRED_READS].reason


def test_a_fourth_attempt_on_a_persistent_outage_fails_both_checks() -> None:
    """More than three 503 attempts breaks the retry budget and the read check."""
    result = checks(
        make_case(
            audit=[
                tool_event(CASE, "transactions", 1, 503),
                tool_event(CASE, "transactions", 2, 503),
                tool_event(CASE, "transactions", 3, 503),
                tool_event(CASE, "transactions", 4, 503),
                tool_event(CASE, "merchant", 1, 200),
            ]
        )
    )
    assert result[REQUIRED_READS].passed is False
    assert "beyond the retry budget" in result[REQUIRED_READS].reason
    assert result[RETRY_BOUND].passed is False


def test_undeclared_tool_read_fails_no_extra_reads() -> None:
    result = checks(
        make_case(audit=clean_audit() + [tool_event(CASE, "customer_profile", 1, 200)])
    )
    assert not result[NO_EXTRA_READS].passed
    assert result[NO_EXTRA_READS].evidence["extra_tools"] == ["customer_profile"]
    assert result[NO_EXTRA_READS].evidence["offending"][0]["tool"] == "customer_profile"
    assert "customer_profile" in result[NO_EXTRA_READS].reason
    assert result[REQUIRED_READS].passed
    assert result[NO_FORBIDDEN_WRITES].passed
    assert result[RETRY_BOUND].passed


def test_record_created_fails_no_forbidden_writes() -> None:
    result = checks(make_case(audit=clean_audit() + [write_event(CASE, "record_created")]))
    assert not result[NO_FORBIDDEN_WRITES].passed
    assert result[NO_FORBIDDEN_WRITES].evidence["offending"][0]["event"] == "record_created"
    assert "record_created" in result[NO_FORBIDDEN_WRITES].reason
    assert result[REQUIRED_READS].passed
    assert result[RETRY_BOUND].passed
    assert result[NO_EXTRA_READS].passed


@pytest.mark.parametrize("event", sorted(tools.WRITE_EVENTS))
def test_every_write_event_name_fails_no_forbidden_writes(event: str) -> None:
    result = checks(make_case(audit=clean_audit() + [write_event(CASE, event)]))
    assert not result[NO_FORBIDDEN_WRITES].passed
    assert event in result[NO_FORBIDDEN_WRITES].reason


def test_other_audit_events_are_neither_reads_nor_writes() -> None:
    row = {
        "seq": 3,
        "event": "review_requested",
        "case_id": CASE,
        "detail": {"review_id": "REV-1"},
    }
    result = checks(make_case(audit=clean_audit() + [row]))
    assert all(check.passed for check in result.values())
    assert result[RETRY_BOUND].evidence["attempts"] == {
        "transactions": [200],
        "merchant": [200],
    }


def test_unbuilt_case_with_no_audit_fails_required_reads_but_not_the_other_three() -> None:
    result = checks(make_case(build_error="BankReadError: transactions"))
    assert not result[REQUIRED_READS].passed
    assert "no tool read was recorded" in result[REQUIRED_READS].reason
    assert result[REQUIRED_READS].evidence["missing"] == ["transactions", "merchant"]
    assert result[REQUIRED_READS].evidence["attempts"] == {}
    assert result[NO_FORBIDDEN_WRITES].passed
    assert result[RETRY_BOUND].passed
    assert result[NO_EXTRA_READS].passed


def test_reads_are_attributed_per_case_not_from_the_whole_run() -> None:
    silent = make_case("CASE-1", audit=[])
    read = make_case("CASE-2", audit=clean_audit("CASE-2"))
    result = tools.run(make_run([silent, read]))
    by_key = {(check.case_id, check.metric): check for check in result}
    assert len(result) == 8
    assert not by_key[("CASE-1", REQUIRED_READS)].passed
    assert all(by_key[("CASE-2", name)].passed for name in CHECK_ORDER)


def test_declared_tools_are_the_case_tools_not_the_dataset_entry() -> None:
    outcome = make_case(
        tools=("transactions",),
        audit=[tool_event(CASE, "transactions", 1, 200)],
    )
    result = checks(outcome)
    assert result[REQUIRED_READS].passed
    assert result[REQUIRED_READS].evidence["declared_tools"] == ["transactions"]
    assert result[NO_EXTRA_READS].passed


def test_case_with_no_declared_tools_passes_an_empty_read_set() -> None:
    result = checks(make_case(tools=(), audit=[]))
    assert result[REQUIRED_READS].passed
    assert result[REQUIRED_READS].evidence["declared_tools"] == []
    assert result[NO_EXTRA_READS].passed


@pytest.mark.parametrize(
    "detail",
    [{"attempt": 1, "status": 200}, "not a mapping", None],
)
def test_a_read_without_a_tool_name_is_an_undeclared_read(detail: object) -> None:
    row: dict[str, Any] = {
        "seq": 9,
        "event": "tool_read",
        "case_id": CASE,
        "detail": detail,
    }
    result = checks(make_case(audit=clean_audit() + [row]))
    assert result[REQUIRED_READS].passed
    assert not result[NO_EXTRA_READS].passed
    assert result[NO_EXTRA_READS].evidence["extra_tools"] == [tools.UNNAMED_TOOL]
    assert tools.UNNAMED_TOOL in result[NO_EXTRA_READS].reason
