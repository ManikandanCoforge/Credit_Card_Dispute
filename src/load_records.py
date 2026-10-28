"""Load the bank case list into working records."""

import json
from http.client import HTTPConnection, HTTPSConnection
from pathlib import Path
from urllib.parse import urlparse

from pydantic import ValidationError

from src.api_models import CaseListResponse
from src.build_records import build_complaint_records
from src.models import Case, WorkingRecord


class BankReadError(Exception):
    """The bank returned no usable body for one read."""


class CaseListError(BankReadError):
    """The bank case list could not be read. Nothing was taken from the dataset."""


class BankUnavailable(BankReadError):
    """A read that a later attempt may answer: a dropped connection, or a 503 marked retryable."""


# A bank that accepts the connection and never answers must not hold one attempt
# open. The wait is bounded per read, so a retry is possible rather than a stall.
_SOCKET_TIMEOUT_SECONDS = 5.0


def read_body(
    base_url: str, path: str, *, timeout: float = _SOCKET_TIMEOUT_SECONDS
) -> bytes:
    """GET one bank path and return the body of a 200 response.

    A URL that is not http(s), or any other status, raises BankReadError, so a
    failed read can never be mistaken for an empty result. A connection failure, a
    read that does not answer within timeout seconds, and a 503 whose body says
    "retryable": true raise the subclass BankUnavailable, so a caller can retry
    those and nothing else.
    """
    origin = urlparse(base_url)
    hostname = origin.hostname
    if origin.scheme not in {"http", "https"} or hostname is None:
        raise BankReadError
    port = origin.port
    if port is None:
        port = 443 if origin.scheme == "https" else 80
    connection_cls = HTTPSConnection if origin.scheme == "https" else HTTPConnection
    connection = connection_cls(hostname, port, timeout=timeout)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        status = response.status
        body = response.read()
    except OSError as error:
        raise BankUnavailable from error
    finally:
        connection.close()
    if status == 503 and _retryable(body):
        raise BankUnavailable
    if status != 200:
        raise BankReadError
    return body


def _retryable(body: bytes) -> bool:
    """Whether an error body marks the failure retryable, as the mock's upstream timeout does."""
    try:
        parsed = json.loads(body)
    except ValueError:
        return False
    return isinstance(parsed, dict) and parsed.get("retryable") is True


def load_cases(base_url: str) -> CaseListResponse:
    """Read the bank case list.

    A connection failure, a non-200 response, or a body that is not a usable
    case list raises CaseListError before the dataset is opened.
    """
    try:
        raw = read_body(base_url, "/v1/cases")
    except BankReadError as error:
        raise CaseListError from error
    try:
        return CaseListResponse.model_validate_json(raw)
    except ValidationError as error:
        raise CaseListError from error


def records_from_case_list(
    case_list: CaseListResponse, data_dir: str | Path
) -> list[WorkingRecord]:
    """Build one working record per complaint in an already read case list."""
    cases: list[Case] = [
        {"case_id": case.case_id, "intake_source": case.intake_source}
        for case in case_list.cases
    ]
    return build_complaint_records(cases, data_dir)


def load_complaint_records(base_url: str, data_dir: str | Path) -> list[WorkingRecord]:
    """Load the bank case list and build one working record per complaint."""
    return records_from_case_list(load_cases(base_url), data_dir)
