"""Working-record shapes built from a complaint intake and its policy."""

from typing import TypedDict


class Case(TypedDict):
    case_id: str
    intake_source: str


class Intake(TypedDict):
    source_id: str | None
    statement: str | None
    reported_date: str | None
    transaction_id: str | None
    authorization: str | None
    promised_service_date: str | None
    purchase_receipt: str | None
    submission_reference: str | None


class Policy(TypedDict):
    version_id: str | None
    procedure_id: str | None


class WorkingRecord(TypedDict):
    case_id: str
    intake: Intake
    policy: Policy
    missing_information: list[str]
    routing: str | None
