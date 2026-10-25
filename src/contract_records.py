"""Read the bank and emit one contract object per complaint.

load_contract_records
  load_complaint_records
    GET /v1/cases
    read the intake
    match the policy version
  for each case
    read the intake, attachment, procedure and policy documents
    GET /v1/cases/{case_id}/transactions and /v1/cases/{case_id}/merchant
    assemble_contract

Both tool reads go through the mock service, which audits each one. A failed
read stops the case: an outage is never treated as an empty transaction history.
"""

from pathlib import Path
from typing import cast
from urllib.parse import quote

from pydantic import ValidationError

from src.api_models import MerchantToolPayload, TransactionToolPayload
from src.build_records import build_merchant, build_transaction
from src.contract import Contract, ContractError, assemble_contract
from src.load_records import BankReadError, load_complaint_records, read_body
from src.models import (
    Intake,
    MerchantTool,
    Transaction,
    TransactionTool,
    WorkingRecord,
)

# The case list names an intake and an attachment that share one prefix.
_INTAKE_SUFFIX = "-INTAKE"
_ATTACHMENT_SUFFIX = "-ATTACHMENT"


class ContractRecordError(Exception):
    """A contract object could not be read from the bank or assembled for one case."""


def load_contract_records(base_url: str, data_dir: str | Path) -> list[Contract]:
    """Return one contract object per case in the bank case list, in bank order."""
    data_dir = Path(data_dir)
    return [
        _contract_record(record, base_url, data_dir)
        for record in load_complaint_records(base_url, data_dir)
    ]


def _contract_record(record: WorkingRecord, base_url: str, data_dir: Path) -> Contract:
    """Read the evidence and the tools for one case, then assemble its contract."""
    # load_complaint_records always stores an intake object, even for a document
    # it could not read, so a record reaching this runner always has one.
    intake = cast(Intake, record["intake"])
    version_id = record["policy"]["version_id"]
    procedure_id = record["policy"]["procedure_id"]
    if version_id is None or procedure_id is None:
        raise ContractRecordError("the reported date selected no policy version")
    attachment_source = _attachment_source(intake["source_id"])
    intake_text = _document(data_dir, "documents", intake["source_id"])
    attachment_text = _document(data_dir, "documents", attachment_source)
    procedure_text = _document(data_dir, "policies", procedure_id)
    policy_text = _document(data_dir, "policies", version_id)
    enriched = build_transaction(record, _transactions(base_url, record["case_id"]))
    enriched = build_merchant(enriched, _merchant(base_url, record["case_id"]))
    try:
        return assemble_contract(
            enriched,
            intake_text=intake_text,
            attachment_text=attachment_text,
            procedure_text=procedure_text,
            policy_text=policy_text,
        )
    except ContractError as error:
        raise ContractRecordError from error


def _transactions(base_url: str, case_id: str) -> TransactionTool:
    """The transactions tool body, validated before it can reach the contract."""
    try:
        payload = TransactionToolPayload.model_validate_json(
            _read_tool(base_url, case_id, "transactions")
        )
    except ValidationError as error:
        raise ContractRecordError from error
    charges: list[Transaction] = [
        {
            "transaction_id": charge.transaction_id,
            "amount": charge.amount,
            "currency": charge.currency,
            "merchant_id": charge.merchant_id,
            "posted_date": charge.posted_date,
        }
        for charge in payload.transactions
    ]
    return {"source_id": payload.source_id, "transactions": charges}


def _merchant(base_url: str, case_id: str) -> MerchantTool:
    """The merchant tool body. The private token is not copied out of it."""
    try:
        payload = MerchantToolPayload.model_validate_json(
            _read_tool(base_url, case_id, "merchant")
        )
    except ValidationError as error:
        raise ContractRecordError from error
    return {
        "source_id": payload.source_id,
        "merchant_id": payload.merchant_id,
        "display_name": payload.display_name,
        "note": payload.note,
    }


def _read_tool(base_url: str, case_id: str, tool: str) -> bytes:
    """One observed tool read. Any failure is an error, never an empty result."""
    try:
        return read_body(base_url, f"/v1/cases/{quote(case_id, safe='')}/{tool}")
    except BankReadError as error:
        raise ContractRecordError from error


def _document(data_dir: Path, folder: str, source_id: str) -> str:
    """One evidence source, by the source id that identifies it."""
    try:
        return (data_dir / folder / f"{source_id}.md").read_text()
    except OSError as error:
        raise ContractRecordError from error


def _attachment_source(intake_source: str) -> str:
    """The attachment that belongs to the intake, by the shared case prefix."""
    if not intake_source.endswith(_INTAKE_SUFFIX):
        raise ContractRecordError("the intake source has no attachment pair")
    return intake_source[: -len(_INTAKE_SUFFIX)] + _ATTACHMENT_SUFFIX
