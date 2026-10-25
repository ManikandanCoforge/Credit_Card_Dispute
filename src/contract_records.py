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
A stopped case does not stop the others: load_contract_results keeps going and
reports the reason for each case it could not build.
"""

import json
import sys
from pathlib import Path
from typing import TypedDict, cast
from urllib.parse import quote

from pydantic import ValidationError

from src.api_models import MerchantToolPayload, TransactionToolPayload
from src.build_records import build_merchant, build_transaction
from src.contract import Contract, ContractError, assemble_contract
from src.load_records import (
    BankReadError,
    CaseListError,
    load_complaint_records,
    read_body,
)
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


class ContractResult(TypedDict):
    case_id: str
    contract: Contract | None
    error: str | None


def load_contract_results(base_url: str, data_dir: str | Path) -> list[ContractResult]:
    """Return one result per case in the bank case list, in bank order.

    A case that cannot be built has a null contract and the reason, and the
    remaining cases still run. The reason is one of this application's own
    messages or an exception class name, never text from a payload or document.
    """
    data_dir = Path(data_dir)
    results: list[ContractResult] = []
    for record in load_complaint_records(base_url, data_dir):
        try:
            contract = _contract_record(record, base_url, data_dir)
        except ContractRecordError as error:
            results.append(
                {"case_id": record["case_id"], "contract": None, "error": _reason(error)}
            )
            continue
        results.append({"case_id": record["case_id"], "contract": contract, "error": None})
    return results


def load_contract_records(base_url: str, data_dir: str | Path) -> list[Contract]:
    """Return one contract object per case in the bank case list, in bank order.

    Any case that cannot be built raises ContractRecordError with its reason.
    """
    contracts: list[Contract] = []
    for result in load_contract_results(base_url, data_dir):
        if result["contract"] is None:
            raise ContractRecordError(f"{result['case_id']}: {result['error']}")
        contracts.append(result["contract"])
    return contracts


def main() -> None:
    """Print the submission array for every case that was built.

    Each case that was not built is named on stderr with its reason, and the exit
    status is 1 when any case was not built, so a partial array is never mistaken
    for a complete one.
    """
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
    data_dir = sys.argv[2] if len(sys.argv) > 2 else "data/dev"
    try:
        results = load_contract_results(base_url, data_dir)
    except CaseListError:
        sys.stderr.write("the bank case list could not be read\n")
        raise SystemExit(1) from None
    contracts = [result["contract"] for result in results if result["contract"] is not None]
    json.dump(contracts, sys.stdout, indent=2)
    sys.stdout.write("\n")
    failed = [result for result in results if result["contract"] is None]
    for result in failed:
        sys.stderr.write(f"{result['case_id']}: not built: {result['error']}\n")
    if failed:
        raise SystemExit(1)


def _reason(error: BaseException) -> str:
    """The first message this application wrote along the cause chain, or a class name.

    Messages from other libraries can carry payload values, such as a pydantic
    input that holds a private token, so they are never copied.
    """
    current: BaseException | None = error
    deepest = error
    while current is not None:
        own = isinstance(current, (ContractRecordError, ContractError, BankReadError))
        if own and str(current):
            return str(current)
        deepest = current
        current = current.__cause__
    return type(deepest).__name__


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
    transactions, transactions_text = _transactions(base_url, record["case_id"])
    enriched = build_transaction(record, transactions)
    enriched = build_merchant(enriched, _merchant(base_url, record["case_id"]))
    try:
        return assemble_contract(
            enriched,
            intake_text=intake_text,
            attachment_text=attachment_text,
            procedure_text=procedure_text,
            policy_text=policy_text,
            transactions_text=transactions_text,
        )
    except ContractError as error:
        raise ContractRecordError from error


def _transactions(base_url: str, case_id: str) -> tuple[TransactionTool, str]:
    """The transactions tool body, validated, and its text with sorted keys.

    The sorted text is the form the evaluator quotes tool bodies from.
    """
    raw = _read_tool(base_url, case_id, "transactions")
    try:
        payload = TransactionToolPayload.model_validate_json(raw)
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
    tool: TransactionTool = {"source_id": payload.source_id, "transactions": charges}
    return tool, json.dumps(json.loads(raw), sort_keys=True)


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


if __name__ == "__main__":
    main()
