"""Load the bank case list into working records."""

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


def read_body(base_url: str, path: str) -> bytes:
    """GET one bank path and return the body of a 200 response.

    A URL that is not http(s), a connection failure, or any other status raises
    BankReadError, so a failed read can never be mistaken for an empty result.
    """
    origin = urlparse(base_url)
    hostname = origin.hostname
    if origin.scheme not in {"http", "https"} or hostname is None:
        raise BankReadError
    port = origin.port
    if port is None:
        port = 443 if origin.scheme == "https" else 80
    connection_cls = HTTPSConnection if origin.scheme == "https" else HTTPConnection
    connection = connection_cls(hostname, port)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        status = response.status
        body = response.read()
    except OSError as error:
        raise BankReadError from error
    finally:
        connection.close()
    if status != 200:
        raise BankReadError
    return body


def load_complaint_records(base_url: str, data_dir: str | Path) -> list[WorkingRecord]:
    """Load the bank case list and build one working record per complaint.

    The case list is GET /v1/cases. A connection failure, a non-200 response,
    or a body that is not a usable case list raises CaseListError before the
    dataset is opened. The failure is not stored on a working record.
    """
    try:
        raw = read_body(base_url, "/v1/cases")
    except BankReadError as error:
        raise CaseListError from error
    try:
        case_list = CaseListResponse.model_validate_json(raw)
    except ValidationError as error:
        raise CaseListError from error
    cases: list[Case] = [
        {"case_id": case.case_id, "intake_source": case.intake_source}
        for case in case_list.cases
    ]
    return build_complaint_records(cases, data_dir)
