"""One record per complaint, keyed by the submission reference.

CARD-D02 and CARD-D09 both carry dispute-double-02. That string is the
Idempotency-Key. A replay and a redelivery return the stored record.
"""

import pytest

from src.api_models import RecordRow
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


def test_the_idempotency_key_is_the_submission_reference():
    assert idempotency_key("  dispute-d01\n") == "dispute-d01"
    assert idempotency_key(_KEY) == _KEY
    assert idempotency_key("dispute-d01") != idempotency_key(_KEY)
    assert idempotency_key("k" * 128) == "k" * 128


@pytest.mark.parametrize("reference", ["", "   ", "not supplied", "  not supplied  "])
def test_a_missing_submission_reference_is_rejected(reference):
    with pytest.raises(ValueError, match="submission reference is required"):
        idempotency_key(reference)


def test_a_submission_reference_longer_than_128_characters_is_rejected():
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
        return 409, {"error": "duplicate_case", "existing_record_id": _KEY}

    def lookup(case_id):
        calls.append(("lookup", case_id))
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


def test_an_idempotency_conflict_returns_the_stored_record():
    def submit(key, request):
        assert key == _KEY
        return 409, {"error": "idempotency_conflict"}

    result = create_record(submit, _request(), _KEY, lookup=lambda _case_id: _ledger_row())

    assert result["created"] is False
    assert result["record_id"] == _KEY


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
    assert "SYNTHETIC" not in str(raised.value)


def test_a_create_response_without_a_record_is_rejected():
    def submit(key, request):
        return 201, {"status": "created"}

    with pytest.raises(CreateRejected) as raised:
        create_record(submit, _request(), _KEY, lookup=lambda _case_id: None)

    assert raised.value.status == 201
    assert raised.value.error is None


def test_an_unreadable_error_body_is_rejected():
    def submit(key, request):
        return 400, {"retryable": True}

    with pytest.raises(CreateRejected) as raised:
        create_record(submit, _request(), _KEY, lookup=lambda _case_id: None)

    assert raised.value.status == 400
    assert raised.value.error is None


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
