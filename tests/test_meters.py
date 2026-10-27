"""One JSON meter line per case, recorded for a later case run to call."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.meters import MeterLeak, latency_percentiles, record_case_meter


def test_one_case_appends_one_meter_line_with_every_field(tmp_path: Path) -> None:
    path = tmp_path / "meters.jsonl"
    record_case_meter(
        path,
        case_id="CARD-D01",
        route="ready_for_review",
        started_at=datetime(2026, 10, 26, 21, 46, 1, 200000, tzinfo=UTC),
        latency_ms=41,
        model_calls=0,
        input_tokens=0,
        output_tokens=0,
        tool_attempts=2,
        retry_count=0,
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "case_id": "CARD-D01",
        "route": "ready_for_review",
        "started_at": "2026-10-26T21:46:01.200Z",
        "latency_ms": 41,
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "tool_attempts": 2,
        "retry_count": 0,
    }


def test_a_second_case_appends_a_second_meter_line(tmp_path: Path) -> None:
    path = tmp_path / "meters.jsonl"
    record_case_meter(
        path,
        case_id="CARD-D01",
        route="ready_for_review",
        started_at=datetime(2026, 10, 26, 21, 46, 1, 200000, tzinfo=UTC),
        latency_ms=41,
        model_calls=0,
        input_tokens=0,
        output_tokens=0,
        tool_attempts=2,
        retry_count=0,
    )
    record_case_meter(
        path,
        case_id="CARD-D04",
        route="request_information",
        started_at=datetime(2026, 10, 26, 21, 46, 2, tzinfo=UTC),
        latency_ms=15,
        model_calls=0,
        input_tokens=0,
        output_tokens=0,
        tool_attempts=1,
        retry_count=0,
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["case_id"] for line in lines] == ["CARD-D01", "CARD-D04"]
    assert json.loads(lines[1]) == {
        "case_id": "CARD-D04",
        "route": "request_information",
        "started_at": "2026-10-26T21:46:02.000Z",
        "latency_ms": 15,
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "tool_attempts": 1,
        "retry_count": 0,
    }


def test_p50_and_p95_are_read_from_the_meter_file(tmp_path: Path) -> None:
    path = tmp_path / "meters.jsonl"
    for case_id, latency_ms in (
        ("CARD-D01", 30),
        ("CARD-D02", 10),
        ("CARD-D03", 40),
        ("CARD-D04", 20),
    ):
        record_case_meter(
            path,
            case_id=case_id,
            route="ready_for_review",
            started_at=datetime(2026, 10, 26, 21, 46, 1, tzinfo=UTC),
            latency_ms=latency_ms,
            model_calls=0,
            input_tokens=0,
            output_tokens=0,
            tool_attempts=2,
            retry_count=0,
        )
    assert latency_percentiles(path) == {"p50": 20, "p95": 40}


def test_latency_percentiles_of_an_empty_meter_file_are_none(tmp_path: Path) -> None:
    path = tmp_path / "meters.jsonl"
    path.write_text("", encoding="utf-8")
    assert latency_percentiles(path) == {"p50": None, "p95": None}


def test_evidence_text_is_refused_and_the_file_stays_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "meters.jsonl"
    record_case_meter(
        path,
        case_id="CARD-D01",
        route="ready_for_review",
        started_at=datetime(2026, 10, 26, 21, 46, 1, 200000, tzinfo=UTC),
        latency_ms=41,
        model_calls=0,
        input_tokens=0,
        output_tokens=0,
        tool_attempts=2,
        retry_count=0,
    )
    before = path.read_text(encoding="utf-8")
    with pytest.raises(MeterLeak):
        record_case_meter(
            path,
            case_id="CARD-D01",
            route="I found a card purchase at Morrow Supplies",
            started_at=datetime(2026, 10, 26, 21, 46, 1, tzinfo=UTC),
            latency_ms=41,
            model_calls=0,
            input_tokens=0,
            output_tokens=0,
            tool_attempts=2,
            retry_count=0,
        )
    assert path.read_text(encoding="utf-8") == before


def test_a_card_number_is_refused_and_the_file_stays_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "meters.jsonl"
    record_case_meter(
        path,
        case_id="CARD-D01",
        route="ready_for_review",
        started_at=datetime(2026, 10, 26, 21, 46, 1, tzinfo=UTC),
        latency_ms=41,
        model_calls=0,
        input_tokens=0,
        output_tokens=0,
        tool_attempts=2,
        retry_count=0,
    )
    before = path.read_text(encoding="utf-8")
    with pytest.raises(MeterLeak):
        record_case_meter(
            path,
            case_id="4111111111111111",
            route="ready_for_review",
            started_at=datetime(2026, 10, 26, 21, 46, 1, tzinfo=UTC),
            latency_ms=41,
            model_calls=0,
            input_tokens=0,
            output_tokens=0,
            tool_attempts=2,
            retry_count=0,
        )
    assert path.read_text(encoding="utf-8") == before


def test_a_customer_reference_is_refused_and_the_file_stays_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "meters.jsonl"
    record_case_meter(
        path,
        case_id="CARD-D01",
        route="ready_for_review",
        started_at=datetime(2026, 10, 26, 21, 46, 1, tzinfo=UTC),
        latency_ms=41,
        model_calls=0,
        input_tokens=0,
        output_tokens=0,
        tool_attempts=2,
        retry_count=0,
    )
    before = path.read_text(encoding="utf-8")
    with pytest.raises(MeterLeak):
        record_case_meter(
            path,
            case_id="CARD-D01",
            route="CUST-8821947300",
            started_at=datetime(2026, 10, 26, 21, 46, 1, tzinfo=UTC),
            latency_ms=41,
            model_calls=0,
            input_tokens=0,
            output_tokens=0,
            tool_attempts=2,
            retry_count=0,
        )
    assert path.read_text(encoding="utf-8") == before



_BASE_METER = {
    "case_id": "CARD-D01",
    "route": "ready_for_review",
    "started_at": datetime(2026, 10, 26, 21, 46, 1, 200000, tzinfo=UTC),
    "latency_ms": 41,
    "model_calls": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "tool_attempts": 2,
    "retry_count": 0,
}


def _record(path: Path, **overrides) -> None:
    record_case_meter(path, **{**_BASE_METER, **overrides})


def _refuses(path: Path, **overrides) -> None:
    _record(path)
    before = path.read_text(encoding="utf-8")
    with pytest.raises(MeterLeak):
        _record(path, **overrides)
    assert path.read_text(encoding="utf-8") == before


def test_a_dashed_card_number_in_the_case_id_is_refused(tmp_path: Path) -> None:
    _refuses(tmp_path / "meters.jsonl", case_id="4111-1111-1111-1111")


def test_a_dotted_card_number_in_the_case_id_is_refused(tmp_path: Path) -> None:
    _refuses(tmp_path / "meters.jsonl", case_id="4111.1111.1111.1111")


def test_a_grouped_amex_card_number_in_the_case_id_is_refused(tmp_path: Path) -> None:
    _refuses(tmp_path / "meters.jsonl", case_id="3782-822463-10005")


def test_a_grouped_diners_card_number_in_the_case_id_is_refused(tmp_path: Path) -> None:
    _refuses(tmp_path / "meters.jsonl", case_id="3056-930902-5904")


def test_a_card_carried_as_an_integer_is_refused(tmp_path: Path) -> None:
    _refuses(tmp_path / "meters.jsonl", input_tokens=4111111111111111)


def test_a_card_broken_by_a_zero_width_space_is_refused(tmp_path: Path) -> None:
    _refuses(tmp_path / "meters.jsonl", case_id="4111\u200b1111\u200b1111\u200b1111")

def test_a_ten_digit_case_id_is_not_a_restricted_value(tmp_path: Path) -> None:
    path = tmp_path / "meters.jsonl"
    _record(path, case_id="CARD-1234567890")
    [line] = path.read_text(encoding="utf-8").splitlines()
    assert json.loads(line)["case_id"] == "CARD-1234567890"


def test_a_restricted_value_is_refused_and_the_file_stays_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "meters.jsonl"
    record_case_meter(
        path,
        case_id="CARD-D01",
        route="ready_for_review",
        started_at=datetime(2026, 10, 26, 21, 46, 1, tzinfo=UTC),
        latency_ms=41,
        model_calls=0,
        input_tokens=0,
        output_tokens=0,
        tool_attempts=2,
        retry_count=0,
    )
    before = path.read_text(encoding="utf-8")
    with pytest.raises(MeterLeak):
        record_case_meter(
            path,
            case_id="CARD-D01",
            route="SYNTHETIC-PRIVATE-CARD-D01",
            started_at=datetime(2026, 10, 26, 21, 46, 1, tzinfo=UTC),
            latency_ms=41,
            model_calls=0,
            input_tokens=0,
            output_tokens=0,
            tool_attempts=2,
            retry_count=0,
        )
    assert path.read_text(encoding="utf-8") == before
