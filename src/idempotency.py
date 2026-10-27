"""Create one case record per complaint, keyed by the submission reference.

CARD-D09 is a redelivery of CARD-D02. Both intakes carry the submission
reference dispute-double-02, and that string is the Idempotency-Key. A
second create for the same reference returns the stored record. It does
not mint a new key and it does not open a second case.
"""

from collections.abc import Callable
from typing import TypedDict

from pydantic import ValidationError

from src.api_models import ErrorBody, RecordCreated, RecordRow
from src.build_records import _NOT_SUPPLIED

_DUPLICATE = {"duplicate_case", "idempotency_conflict"}

# The intake sentinel, plus the other ways a form says the reference is absent.
_MISSING_REFERENCES = frozenset({_NOT_SUPPLIED.casefold(), "n/a", "none", "-"})


class RecordRequest(TypedDict):
    """The create body, without the key. The key travels separately."""

    case_id: str
    review_id: str
    draft: dict[str, object]


class StoredRecord(TypedDict):
    """The one record for a complaint. created is true only on the first write."""

    record_id: str
    case_id: str
    review_id: str
    created: bool


class CreateRejected(Exception):
    """The mock refused the create. The caller keeps the same key if it retries."""

    def __init__(self, status: int, error: str | None = None) -> None:
        self.status = status
        self.error = error
        detail = f"record create failed with HTTP {status}"
        if error is not None:
            detail = f"{detail}: {error}"
        super().__init__(detail)


class MissingRecord(Exception):
    """A duplicate was reported, and the ledger has no row to return."""

    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        super().__init__(f"no stored record for {case_id}")


def idempotency_key(submission_reference: str) -> str:
    """Return the submission reference as the Idempotency-Key.

    A blank value cannot name a complaint. Neither can the intake sentinel
    or the placeholders N/A, none, and -. The mock accepts at most 128
    characters.
    """
    reference = submission_reference.strip()
    if reference == "" or reference.casefold() in _MISSING_REFERENCES:
        raise ValueError("a submission reference is required")
    if len(reference) > 128:
        raise ValueError("a submission reference must be at most 128 characters")
    return reference


def create_record(
    submit: Callable[[str, RecordRequest], tuple[int, object]],
    request: RecordRequest,
    submission_reference: str,
    *,
    lookup: Callable[[str], RecordRow | None],
) -> StoredRecord:
    """Create the case, or return the record already stored for this reference.

    submit sends POST /v1/records with the key as the Idempotency-Key.
    lookup is GET /v1/records/{case_id}, which follows a redelivery to the
    original complaint. HTTP 201 is the first write. HTTP 200 is an exact
    replay. HTTP 409 means the complaint already has a record.
    """
    key = idempotency_key(submission_reference)
    status, payload = submit(key, request)
    if status in {200, 201}:
        return _created(status, payload)
    error = _error_body(status, payload)
    if status == 409 and error.error in _DUPLICATE:
        return _existing(request["case_id"], lookup)
    raise CreateRejected(status, error.error)


def _created(status: int, payload: object) -> StoredRecord:
    try:
        row = RecordCreated.model_validate(payload)
    except ValidationError:
        raise CreateRejected(status) from None
    return {
        "record_id": row.record_id,
        "case_id": row.case_id,
        "review_id": row.review_id,
        "created": status == 201,
    }


def _error_body(status: int, payload: object) -> ErrorBody:
    try:
        return ErrorBody.model_validate(payload)
    except ValidationError:
        raise CreateRejected(status) from None


def _existing(case_id: str, lookup: Callable[[str], RecordRow | None]) -> StoredRecord:
    row = lookup(case_id)
    if row is None:
        raise MissingRecord(case_id)
    return {
        "record_id": row.id,
        "case_id": row.case_id,
        "review_id": row.review_id,
        "created": False,
    }
