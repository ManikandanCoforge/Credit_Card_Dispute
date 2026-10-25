"""Working-record shapes built from a complaint intake and its policy, and the contract shape."""

from typing import NotRequired, TypedDict


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


class Transaction(TypedDict):
    transaction_id: str
    amount: int
    currency: str
    merchant_id: str
    posted_date: str


class Merchant(TypedDict):
    merchant_id: str
    display_name: str
    note: str


class TransactionTool(TypedDict):
    source_id: str
    transactions: list[Transaction]


class MerchantTool(TypedDict):
    source_id: str
    merchant_id: str
    display_name: str
    note: str


class Facts(TypedDict):
    transaction_id: str | None
    amount: int | None
    currency: str | None
    reported_date: str | None


class Citation(TypedDict):
    claim: str
    source_id: str
    quote: str


class FollowUpQuestion(TypedDict):
    field: str
    question: str


class Contract(TypedDict):
    """One object of the submission array, as docs/OUTPUT_CONTRACT.md defines it."""

    case_id: str
    classification: str
    routing: str
    policy_ids: list[str]
    facts: Facts
    missing_information: list[str]
    deadline: str | None
    citations: list[Citation]
    follow_up_questions: list[FollowUpQuestion]
    narrative: str


class WorkingRecord(TypedDict):
    case_id: str
    intake: Intake | None
    policy: Policy
    missing_information: list[str]
    routing: str | None
    transactions: NotRequired[list[Transaction]]
    merchant: NotRequired[Merchant]
