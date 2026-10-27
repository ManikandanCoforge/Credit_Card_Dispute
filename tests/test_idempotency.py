"""One record per idempotency key.

The caller supplies the key. These tests use dispute-double-02 to show that
a replay and a shared key return the stored record.
"""

import traceback

import pytest

from src.api_models import RecordRow
from src.build_records import _NOT_SUPPLIED
from src.idempotency import (
    CreateRejected,
    MissingRecord,
    create_record,
    idempotency_key,
)

_KEY = "dispute-double-02"
_ORIGINAL = {
    "record_id": _KEY,
    "case_id": "CARD-D02",
    "status": "created",
    "review_id": "rev_d02",
}


def test_the_idempotency_key_is_the_supplied_string():
    assert idempotency_key("  dispute-d01\n") == "dispute-d01"
    assert idempotency_key(_KEY) == _KEY
    assert idempotency_key("dispute-d01") != idempotency_key(_KEY)
    assert idempotency_key("k" * 128) == "k" * 128


@pytest.mark.parametrize(
    "reference",
    [
        "",
        "   ",
        _NOT_SUPPLIED,
        "Not Supplied",
        "NOT SUPPLIED",
        "  not supplied  ",
        "N/A",
        "none",
        "-",
    ],
)
def test_a_missing_idempotency_key_is_rejected(reference):
    with pytest.raises(ValueError, match="idempotency key is required"):
        idempotency_key(reference)


def test_an_idempotency_key_longer_than_128_characters_is_rejected():
    with pytest.raises(ValueError, match="at most 128"):
        idempotency_key("k" * 129)


def test_a_missing_reference_does_not_submit():
    def submit(key, request):
        raise AssertionError((key, request))

    with pytest.raises(ValueError):
        create_record(submit, _request(), "not supplied", lookup=lambda _case_id: None)


def test_the_first_create_is_the_only_write():
    writes = {"n": 0}
    stored = {}

    def submit(key, request):
        assert "Idempotency-Key" not in request
        assert request == _request()
        if key in stored:
            return 200, stored[key]
        writes["n"] += 1
        stored[key] = _ORIGINAL
        return 201, _ORIGINAL

    first = create_record(submit, _request(), f"  {_KEY}  ", lookup=lambda _case_id: None)
    second = create_record(submit, _request(), _KEY, lookup=lambda _case_id: None)

    assert writes["n"] == 1
    assert list(stored) == [_KEY]
    assert first == {
        "record_id": _KEY,
        "case_id": "CARD-D02",
        "review_id": "rev_d02",
        "created": True,
    }
    assert second == {**first, "created": False}


def test_a_redelivery_is_the_existing_record_and_not_an_error():
    calls = []

    def submit(key, request):
        calls.append((key, request["case_id"]))
        if request["case_id"] == "CARD-D02":
            return 201, _ORIGINAL
        return 409, {"error": "idempotency_conflict"}

    def lookup(case_id):
        calls.append(("lookup", case_id))
        assert case_id == "CARD-D09"
        return _ledger_row()

    first = create_record(submit, _request(), _KEY, lookup=lookup)
    second = create_record(submit, _request("CARD-D09", "rev_d09"), _KEY, lookup=lookup)

    assert first["created"] is True
    assert second == {
        "record_id": _KEY,
        "case_id": "CARD-D02",
        "review_id": "rev_d02",
        "created": False,
    }
    assert calls == [
        (_KEY, "CARD-D02"),
        (_KEY, "CARD-D09"),
        ("lookup", "CARD-D09"),
    ]


def test_a_duplicate_with_no_ledger_row_names_the_case():
    def submit(key, request):
        return 409, {"error": "duplicate_case"}

    with pytest.raises(MissingRecord) as raised:
        create_record(submit, _request("CARD-D09"), _KEY, lookup=lambda _case_id: None)

    assert raised.value.case_id == "CARD-D09"
    assert "SYNTHETIC" not in str(raised.value)


def test_an_unrecognized_conflict_is_rejected():
    def submit(key, request):
        return 409, {"error": "read_only_mission"}

    with pytest.raises(CreateRejected) as raised:
        create_record(submit, _request(), _KEY, lookup=lambda _case_id: _ledger_row())

    assert raised.value.status == 409
    assert raised.value.error == "read_only_mission"
    assert str(raised.value) == "record create failed with HTTP 409: read_only_mission"


def test_a_refused_create_keeps_the_status_and_drops_the_payload_message():
    def submit(key, request):
        return 403, {
            "error": "approval_missing_or_draft_changed",
            "message": "SYNTHETIC-PRIVATE-TOKEN",
        }

    with pytest.raises(CreateRejected) as raised:
        create_record(submit, _request(), _KEY, lookup=lambda _case_id: None)

    assert raised.value.status == 403
    assert raised.value.error == "approval_missing_or_draft_changed"
    assert str(raised.value) == (
        "record create failed with HTTP 403: approval_missing_or_draft_changed"
    )
    assert "SYNTHETIC" not in str(raised.value)


def test_a_create_response_without_a_record_is_rejected():
    def submit(key, request):
        return 201, {"status": "created", "message": "CUST-1234-SECRET"}

    with pytest.raises(CreateRejected) as raised:
        create_record(submit, _request(), _KEY, lookup=lambda _case_id: None)

    assert raised.value.status == 201
    assert raised.value.error is None
    _assert_the_payload_is_not_in_the_traceback(raised.value)


def test_an_unreadable_error_body_is_rejected():
    def submit(key, request):
        return 400, {"message": "CUST-1234-SECRET"}

    with pytest.raises(CreateRejected) as raised:
        create_record(submit, _request(), _KEY, lookup=lambda _case_id: None)

    assert raised.value.status == 400
    assert raised.value.error is None
    _assert_the_payload_is_not_in_the_traceback(raised.value)


def _assert_the_payload_is_not_in_the_traceback(error: CreateRejected) -> None:
    rendered = "".join(traceback.format_exception(error))
    assert error.__cause__ is None
    assert "CUST-1234-SECRET" not in rendered
    assert "ValidationError" not in rendered


def _request(case_id="CARD-D02", review_id="rev_d02"):
    return {"case_id": case_id, "review_id": review_id, "draft": {"case_id": case_id}}


def _ledger_row():
    return RecordRow.model_validate(
        {
            "id": _KEY,
            "case_id": "CARD-D02",
            "draft": '{"case_id":"CARD-D02"}',
            "review_id": "rev_d02",
        }
    )
