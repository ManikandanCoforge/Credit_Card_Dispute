"""Which models may answer the hybrid's questions, and how a qualification run is scored.

Expected outcomes come from ADR-003's scoring rule and from the four qualification
reports on file in evals/qualification/reports, which were scored before this module
existed. The registry checks use models.toml as committed.
"""

import json
from pathlib import Path

import pytest

from src.model_cue import SCHEMA_HASH
from src.model_registry import find_qualified, load_registry, score, summarize

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "evals" / "qualification" / "reports"


def _row(case_id, expected, proposal, *, outcome=None, gap=False, answered=True, latency_ms=800.0):
    return {
        "case_id": case_id,
        "expected": expected,
        "gap": gap,
        "proposal": proposal,
        "outcome": outcome or score(expected, proposal),
        "answered": answered,
        "latency_ms": latency_ms,
    }


def _summary(rows):
    return summarize(
        rows,
        provider="azure_openai",
        model_id="gpt-6-luna",
        qualified_on="2026-10-26",
        data_location="East US",
        approved_by="",
    )


def test_every_registered_model_passed_for_the_current_schema():
    entries = load_registry(ROOT / "models.toml")

    assert find_qualified(entries, "azure_openai", "gpt-6-luna") is not None
    assert all(entry["passed"] is True for entry in entries)
    assert all(entry["schema_hash"] == SCHEMA_HASH for entry in entries)


def test_every_registry_entry_is_the_record_its_qualification_report_holds():
    for entry in load_registry(ROOT / "models.toml"):
        report = REPORTS / f"{entry['provider']}__{entry['model_id']}__cue_suite.json"
        recorded = json.loads(report.read_text(encoding="utf-8"))["entry"]

        assert entry == {key: value for key, value in recorded.items() if value is not None}


@pytest.mark.parametrize("report", sorted(REPORTS.glob("*.json")), ids=lambda path: path.stem)
def test_scoring_reproduces_every_outcome_in_the_reports_on_file(report):
    cases = json.loads(report.read_text(encoding="utf-8"))["cases"]

    assert [score(case["expected"], case["proposal"]) for case in cases] == [
        case["outcome"] for case in cases
    ]


def test_a_missing_registry_qualifies_nothing(tmp_path):
    assert load_registry(tmp_path / "models.toml") == []


def test_a_registry_value_that_is_not_a_table_is_ignored(tmp_path):
    registry = tmp_path / "models.toml"
    registry.write_text('model = ["azure_openai/gpt-6-luna"]\n', encoding="utf-8")

    assert load_registry(registry) == []


@pytest.mark.parametrize(
    "change",
    [
        {"schema_hash": "sha256:0000000000000000"},
        {"passed": False},
        {"passed": "true"},
        {"model_id": "gpt-6-luna-preview"},
        {"provider": "anthropic_foundry"},
    ],
)
def test_only_a_passed_record_for_this_provider_model_and_schema_qualifies(change):
    entry = {
        "provider": "azure_openai",
        "model_id": "gpt-6-luna",
        "schema_hash": SCHEMA_HASH,
        "passed": True,
    }

    assert find_qualified([entry], "azure_openai", "gpt-6-luna") == entry
    assert find_qualified([{**entry, **change}], "azure_openai", "gpt-6-luna") is None


@pytest.mark.parametrize(
    "expected, proposal, outcome",
    [
        ("unauthorized", "unauthorized", "correct"),
        ("duplicate_charge", "duplicate_charge", "correct"),
        ("service_not_received", "service_not_received", "correct"),
        ("unsupported", "cash_withdrawal", "correct"),
        ("unsupported", "other_dispute", "correct"),
        ("ambiguous", "none", "correct"),
        ("ambiguous", None, "correct"),
        ("unauthorized", "none", "cautious"),
        ("unauthorized", None, "cautious"),
        ("unauthorized", "other_dispute", "cautious"),
        ("ambiguous", "cash_withdrawal", "cautious"),
        ("unauthorized", "made_up_type", "cautious"),
        ("duplicate_charge", "unauthorized", "unsafe"),
        ("unsupported", "duplicate_charge", "unsafe"),
        ("ambiguous", "service_not_received", "unsafe"),
    ],
)
def test_each_answer_is_correct_cautious_or_unsafe(expected, proposal, outcome):
    assert score(expected, proposal) == outcome


def test_a_clean_run_passes_and_counts_its_gap_cases():
    rows = [
        _row("A", "unauthorized", "unauthorized", latency_ms=700.0),
        _row("B", "unsupported", "other_dispute", gap=True, latency_ms=900.0),
        _row("C", "ambiguous", "none", gap=True, latency_ms=1100.0),
        _row("D", "duplicate_charge", "none", latency_ms=None, answered=True),
    ]

    assert _summary(rows) == {
        "provider": "azure_openai",
        "model_id": "gpt-6-luna",
        "schema_hash": SCHEMA_HASH,
        "qualified_on": "2026-10-26",
        "cases": 4,
        "answered": 4,
        "cue_correct": 3,
        "cautious": 1,
        "unsafe": 0,
        "gap_cases": 2,
        "gap_correct": 2,
        "median_latency_s": 0.9,
        "data_location": "East US",
        "approved_by": "",
        "passed": True,
    }


def test_one_unsafe_answer_fails_the_run():
    rows = [_row(f"C{n}", "unauthorized", "unauthorized") for n in range(19)]
    rows.append(_row("C19", "unsupported", "duplicate_charge"))

    record = _summary(rows)

    assert record["unsafe"] == 1
    assert record["passed"] is False


def test_fewer_than_nine_in_ten_answered_fails_the_run():
    answered = [_row(f"C{n}", "unauthorized", "unauthorized") for n in range(9)]
    unanswered = [_row(f"U{n}", "unauthorized", None, answered=False) for n in range(2)]

    assert _summary(answered + unanswered[:1])["passed"] is True
    assert _summary(answered + unanswered)["passed"] is False


def test_an_empty_run_never_passes():
    record = _summary([])

    assert record["cases"] == 0
    assert record["median_latency_s"] is None
    assert record["passed"] is False
