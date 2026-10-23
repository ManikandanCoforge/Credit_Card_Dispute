"""Working-record shapes built from a complaint intake and its policy."""

from typing import TypedDict


class Case(TypedDict):
    case_id: str
    intake_source: str


class Intake(TypedDict):
    source_id: str
    statement: str
    reported_date: str
    transaction_id: str
    authorization: str
    promised_service_date: str
    purchase_receipt: str
    submission_reference: str


class Policy(TypedDict):
    version_id: str | None
    procedure_id: str | None


class WorkingRecord(TypedDict):
    case_id: str
    intake: Intake | None
    policy: Policy
