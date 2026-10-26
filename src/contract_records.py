"""Read the bank and emit one contract object per complaint.

load_contract_results
  load_cases
    GET /v1/cases
  records_from_case_list
    read the intake
    match the policy version
  for each case
    read every other listed document: a customer statement is kept, anything else refuses the case
    read the intake, attachment, procedure and policy documents
    GET /v1/cases/{case_id}/transactions and /v1/cases/{case_id}/merchant
    assemble_draft: the rules, then the narrative (template, or a configured writer)

Both tool reads go through the mock service, which audits each one. A failed
read stops the case: an outage is never treated as an empty transaction history.
A stopped case does not stop the others: load_contract_results keeps going and
reports the reason for each case it could not build.
"""

import json
import re
import sys
from pathlib import Path
from typing import TypedDict, cast
from urllib.parse import quote

from pydantic import ValidationError

from src.api_models import MerchantToolPayload, TransactionToolPayload
from src.build_records import build_merchant, build_transaction
from src.contract import Contract, ContractError, assemble_draft
from src.load_records import (
    BankReadError,
    CaseListError,
    load_cases,
    read_body,
    records_from_case_list,
)
from src.models import (
    Intake,
    MerchantTool,
    Transaction,
    TransactionTool,
    WorkingRecord,
)
from src.narrative import NarrativeMeter, ProseWriter
from src.untrusted import RestrictedValueError, guard

# The case list names an intake and an attachment that share one prefix.
_INTAKE_SUFFIX = "-INTAKE"
_ATTACHMENT_SUFFIX = "-ATTACHMENT"
_CUSTOMER_REFERENCE_LABEL = "Customer reference:"
# A further listed document is a customer statement when its heading says so (any case).
_CUSTOMER_HEADING = "# customer"
# Source ids become file names, so only plain ids are read: letters, digits, dot, dash and
# underscore, starting with a letter or digit, never "..". "../x" or "a/b" is never a path.
_SOURCE_ID = re.compile(r"(?!.*\.\.)[A-Za-z0-9][A-Za-z0-9._-]*")


class ContractRecordError(Exception):
    """A contract object could not be read from the bank or assembled for one case."""


class ContractResult(TypedDict):
    case_id: str
    contract: Contract | None
    error: str | None
    narrative_meter: NarrativeMeter | None


class CasePlan(TypedDict):
    """One case's working record and the evidence the case list names for it."""

    record: WorkingRecord
    documents: list[str]


def contract_case_plans(base_url: str, data_dir: str | Path) -> list[CasePlan]:
    """Read the case list and pair each working record with its named evidence.

    No document or tool read happens here, so a caller that times cases measures
    each case's evidence reads without the shared case-list read. A case still
    names its own documents in bank order.
    """
    data_dir = Path(data_dir)
    case_list = load_cases(base_url)
    documents = {case.case_id: case.documents for case in case_list.cases}
    return [
        {"record": record, "documents": documents.get(record["case_id"], [])}
        for record in records_from_case_list(case_list, data_dir)
    ]


def build_contract_result(
    plan: CasePlan, base_url: str, data_dir: str | Path, writer: ProseWriter | None = None
) -> ContractResult:
    """Build one case's contract from the bank and the dataset, or report the reason.

    The reason is one of this application's own messages or an exception class
    name, never text from a payload or document. writer, when given, may reword the
    narrative; see src/narrative.py.
    """
    case_id = plan["record"]["case_id"]
    try:
        contract, meter = _contract_record(
            plan["record"], base_url, Path(data_dir), plan["documents"], writer
        )
    except ContractRecordError as error:
        return {
            "case_id": case_id,
            "contract": None,
            "error": _reason(error),
            "narrative_meter": None,
        }
    return {"case_id": case_id, "contract": contract, "error": None, "narrative_meter": meter}


def load_contract_results(
    base_url: str, data_dir: str | Path, writer: ProseWriter | None = None
) -> list[ContractResult]:
    """Return one result per case in the bank case list, in bank order.

    A case that cannot be built has a null contract and the reason, and the
    remaining cases still run. The reason is one of this application's own
    messages or an exception class name, never text from a payload or document.

    writer, when given, may reword each narrative; see src/narrative.py. Each
    built case carries its narrative meter (path, latency, model calls), ready for
    the #45 meter line. main() does not print it, so the meter line must be built
    from these results.
    """
    return [
        build_contract_result(plan, base_url, data_dir, writer)
        for plan in contract_case_plans(base_url, data_dir)
    ]


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


def _contract_record(
    record: WorkingRecord,
    base_url: str,
    data_dir: Path,
    documents: list[str],
    writer: ProseWriter | None,
) -> tuple[Contract, NarrativeMeter]:
    """Read the evidence and the tools for one case, then assemble its contract.

    documents is the evidence the case list names for this case. Besides the
    intake and the attachment, a listed customer statement, such as a follow-up
    email, is read and passed on. Any other listed source is refused rather than
    ignored, so evidence can never be silently left out of the draft.
    """
    # load_complaint_records always stores an intake object, even for a document
    # it could not read, so a record reaching this runner always has one.
    intake = cast(Intake, record["intake"])
    version_id = record["policy"]["version_id"]
    procedure_id = record["policy"]["procedure_id"]
    if version_id is None or procedure_id is None:
        raise ContractRecordError("the reported date selected no policy version")
    attachment_source = _attachment_source(intake["source_id"])
    consumed = {intake["source_id"], attachment_source}
    customer_texts = _customer_statements(
        data_dir, [source_id for source_id in documents if source_id not in consumed]
    )
    intake_text = _document(data_dir, "documents", intake["source_id"])
    attachment_text = _document(data_dir, "documents", attachment_source)
    procedure_text = _document(data_dir, "policies", procedure_id)
    policy_text = _document(data_dir, "policies", version_id)
    transactions, transactions_text = _transactions(base_url, record["case_id"])
    enriched = build_transaction(record, transactions)
    merchant, private_token = _merchant(base_url, record["case_id"])
    enriched = build_merchant(enriched, merchant)
    try:
        contract, meter = assemble_draft(
            enriched,
            intake_text=intake_text,
            attachment_text=attachment_text,
            procedure_text=procedure_text,
            policy_text=policy_text,
            transactions_text=transactions_text,
            customer_texts=customer_texts,
            writer=writer,
        )
    except ContractError as error:
        raise ContractRecordError from error
    try:
        guard(contract, known=[private_token, _customer_reference(intake_text)])
    except RestrictedValueError as error:
        raise ContractRecordError(str(error)) from None
    return contract, meter


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


def _merchant(base_url: str, case_id: str) -> tuple[MerchantTool, str]:
    """The merchant tool body, and its private token for the restricted-value guard.

    The private token is never copied into the merchant record.
    """
    try:
        payload = MerchantToolPayload.model_validate_json(
            _read_tool(base_url, case_id, "merchant")
        )
    except ValidationError as error:
        raise ContractRecordError from error
    token = (payload.model_extra or {}).get("private_token")
    merchant: MerchantTool = {
        "source_id": payload.source_id,
        "merchant_id": payload.merchant_id,
        "display_name": payload.display_name,
        "note": payload.note,
    }
    return merchant, token if isinstance(token, str) else ""


def _customer_reference(intake_text: str) -> str:
    """The customer reference on the intake form, so the guard can refuse it exactly."""
    for line in intake_text.splitlines():
        if line.strip().startswith(_CUSTOMER_REFERENCE_LABEL):
            return line.strip()[len(_CUSTOMER_REFERENCE_LABEL) :].strip()
    return ""


def _read_tool(base_url: str, case_id: str, tool: str) -> bytes:
    """One observed tool read. Any failure is an error, never an empty result."""
    try:
        return read_body(base_url, f"/v1/cases/{quote(case_id, safe='')}/{tool}")
    except BankReadError as error:
        raise ContractRecordError from error


def _document(data_dir: Path, folder: str, source_id: str) -> str:
    """One evidence source, by the source id that identifies it.

    An id that is not a plain source id is refused before any path is built.
    """
    try:
        return _path(data_dir, folder, source_id).read_text(encoding="utf-8")
    except OSError as error:
        raise ContractRecordError from error


def _customer_statements(data_dir: Path, source_ids: list[str]) -> list[str]:
    """The further listed documents, each of which must be a customer statement.

    A listed document that is missing, or whose heading does not mark it as
    customer correspondence, is evidence this step cannot read, so the case is
    refused instead of being drafted without it.
    """
    statements: list[str] = []
    unread: list[str] = []
    for source_id in source_ids:
        try:
            text = _path(data_dir, "documents", source_id).read_text(encoding="utf-8")
        except OSError:
            unread.append(source_id)
            continue
        if text.lstrip().lower().startswith(_CUSTOMER_HEADING):
            statements.append(text)
        else:
            unread.append(source_id)
    if unread:
        raise ContractRecordError(
            "the case names evidence this step cannot read: " + ", ".join(sorted(unread))
        )
    return statements


def _path(data_dir: Path, folder: str, source_id: str) -> Path:
    if _SOURCE_ID.fullmatch(source_id) is None:
        raise ContractRecordError("a source id is not a plain document id")
    return data_dir / folder / f"{source_id}.md"


def _attachment_source(intake_source: str) -> str:
    """The attachment that belongs to the intake, by the shared case prefix."""
    if not intake_source.endswith(_INTAKE_SUFFIX):
        raise ContractRecordError("the intake source has no attachment pair")
    return intake_source[: -len(_INTAKE_SUFFIX)] + _ATTACHMENT_SUFFIX


if __name__ == "__main__":
    main()
