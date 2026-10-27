"""Submit a finished draft for review, then notice a later human decision.

Submitting returns as soon as the mock has stored the review. It does not
wait, and it does not poll. A later check reads that review once. An
approval is the alert to create the case, and that check performs the
record post. The idempotency key is the case id and the review id, one key
per approved draft. A rejection returns the draft and creates nothing.
This module never runs the operator command. Bounded polling, and calling
this from the case runner, are a later change.
"""

import hashlib
import json
from http.client import HTTPConnection
from typing import NotRequired, TypedDict
from urllib.parse import quote, urlparse

from pydantic import ValidationError

from src.api_models import RecordRow, ReviewCreated, ReviewRow
from src.idempotency import RecordRequest, StoredRecord, create_record

# A hung mock must not hold the call open. This is the socket timeout.
_SOCKET_TIMEOUT_SECONDS = 5.0


class ReviewRefused(Exception):
    """The draft cannot proceed.

    Status 403 and reason ``changed`` are this module's own refusal. The
    draft no longer matches the hash from submission. The mock did not
    return 403.
    """

    def __init__(self, status: int | None, reason: str) -> None:
        self.status = status
        self.reason = reason
        super().__init__(reason)


class SubmittedReview(TypedDict):
    """The review opened for a finished draft. The human has not decided."""

    review_id: str
    draft_hash: str
    draft: dict[str, object]
    status: str


class ReviewAlert(TypedDict):
    """What one read of a submitted review says the caller should do."""

    alert: str
    review_id: str
    draft_hash: str
    draft: dict[str, object]
    record_id: NotRequired[str]
    created: NotRequired[bool]


def submit_review(
    base_url: str, case_id: str, draft: dict[str, object]
) -> SubmittedReview:
    """Open the review and return. The human decides in another terminal."""
    created = _submit(base_url, case_id, draft)
    return {
        "review_id": created.review_id,
        "draft_hash": created.draft_hash,
        "draft": draft,
        "status": created.status,
    }


def review_alert(
    base_url: str,
    case_id: str,
    draft: dict[str, object],
    *,
    review_id: str,
    draft_hash: str,
) -> ReviewAlert:
    """Read the review once and act on the status it has now.

    Approval alerts the caller that the record was submitted and creates the
    case. The record key is ``case_id:review_id``, so a copied submission
    reference cannot block another case, and a case with no reference can
    still be recorded. Rejection and a still-pending review return
    immediately. A changed draft raises 403 locally, before any record post.
    A wrong case, an unknown status, or a missing review also refuses.
    """
    row = _fetch(base_url, review_id)
    if _digest(draft) != draft_hash or row.hash != draft_hash:
        raise ReviewRefused(403, "changed")
    if row.case_id != case_id:
        raise ReviewRefused(None, "wrong_case")
    if row.status == "approved":
        stored = _store_record(base_url, case_id, review_id, draft)
        return {
            "alert": "submit_record",
            "review_id": review_id,
            "draft_hash": draft_hash,
            "draft": draft,
            "record_id": stored["record_id"],
            "created": stored["created"],
        }
    if row.status == "rejected":
        return _alert("rejected", review_id, draft_hash, draft)
    if row.status == "pending":
        return _alert("pending", review_id, draft_hash, draft)
    raise ReviewRefused(None, "unknown")


def _alert(
    kind: str, review_id: str, draft_hash: str, draft: dict[str, object]
) -> ReviewAlert:
    return {
        "alert": kind,
        "review_id": review_id,
        "draft_hash": draft_hash,
        "draft": draft,
    }


def _digest(draft: dict[str, object]) -> str:
    """The draft hash the mock stores: SHA-256 of compact, key-sorted JSON."""
    canonical = json.dumps(draft, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _store_record(
    base_url: str,
    case_id: str,
    review_id: str,
    draft: dict[str, object],
) -> StoredRecord:
    """Create the case for an approved draft, or return the one already stored."""

    def submit(key: str, request: RecordRequest) -> tuple[int, object]:
        status, raw = _exchange(
            base_url,
            "POST",
            "/v1/records",
            dict(request),
            headers={"Idempotency-Key": key},
        )
        return status, json.loads(raw)

    def lookup(record_case_id: str) -> RecordRow | None:
        status, raw = _exchange(
            base_url,
            "GET",
            f"/v1/records/{quote(record_case_id, safe='')}",
            None,
        )
        if status == 404:
            return None
        if status != 200:
            raise ReviewRefused(status, "unreadable")
        return _parsed(RecordRow, status, raw)

    request: RecordRequest = {
        "case_id": case_id,
        "review_id": review_id,
        "draft": draft,
    }
    return create_record(submit, request, f"{case_id}:{review_id}", lookup=lookup)


def _submit(base_url: str, case_id: str, draft: dict[str, object]) -> ReviewCreated:
    status, raw = _exchange(
        base_url,
        "POST",
        "/v1/reviews",
        {"case_id": case_id, "draft": draft},
    )
    if status != 201:
        raise ReviewRefused(status, "submit_failed")
    return _parsed(ReviewCreated, status, raw)


def _fetch(base_url: str, review_id: str) -> ReviewRow:
    status, raw = _exchange(
        base_url, "GET", f"/v1/reviews/{quote(review_id, safe='')}", None
    )
    if status == 404:
        raise ReviewRefused(status, "missing")
    if status != 200:
        raise ReviewRefused(status, "unreadable")
    return _parsed(ReviewRow, status, raw)


def _parsed[Row: (ReviewCreated, ReviewRow, RecordRow)](
    model: type[Row], status: int, raw: bytes
) -> Row:
    """Read a 2xx body. A body that is not that row is a refusal."""
    try:
        return model.model_validate_json(raw)
    except ValidationError:
        raise ReviewRefused(status, "unreadable") from None


def _exchange(
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, object] | None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    origin = urlparse(base_url)
    hostname = origin.hostname
    port = origin.port
    if hostname is None or port is None:
        raise ReviewRefused(None, "unreachable")
    connection = HTTPConnection(hostname, port, timeout=_SOCKET_TIMEOUT_SECONDS)
    body = None if payload is None else json.dumps(payload).encode()
    request_headers = {} if body is None else {"Content-Type": "application/json"}
    if headers is not None:
        request_headers.update(headers)
    try:
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        return response.status, response.read()
    except OSError as error:
        raise ReviewRefused(None, "unreachable") from error
    finally:
        connection.close()
