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
    assemble_draft: the rules, with a configured model's two closed questions
      (ADR-003), then the narrative (template, or a configured writer)

Both tool reads go through the mock service, which audits each one. A failed
read stops the case: an outage is never treated as an empty transaction history.
A stopped case does not stop the others: load_contract_results keeps going and
reports the reason for each case it could not build.
"""

import json
import os
import re
import sys
import time
from datetime import UTC, datetime
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
from src.meters import record_case_meter
from src.model_clients import ModelSetupError, model_from_env
from src.model_cue import ModelCall, ModelClient
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
    model_calls: list[ModelCall]


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
    plan: CasePlan,
    base_url: str,
    data_dir: str | Path,
    writer: ProseWriter | None = None,
    model: ModelClient | None = None,
    *,
    meter_path: Path | None = None,
) -> ContractResult:
    """Build one case's contract from the bank and the dataset, or report the reason.

    The reason is one of this application's own messages or an exception class
    name, never text from a payload or document. writer, when given, may reword the
    narrative; see src/narrative.py. model, when given, may answer the hybrid's two
    closed questions (ADR-003); its calls are kept even when the case is not built,
    because they were still made.

    When meter_path is set, one meter line is appended for this case after it
    finishes, including a case that stops.
    """
    started_at = datetime.now(UTC)
    started = time.perf_counter()
    tally = {"tool_attempts": 0, "retry_count": 0}
    case_id = plan["record"]["case_id"]
    calls: list[ModelCall] = []
    try:
        contract, meter = _contract_record(
            plan["record"],
            base_url,
            Path(data_dir),
            plan["documents"],
            writer,
            model,
            calls,
            tally,
        )
    except ContractRecordError as error:
        result: ContractResult = {
            "case_id": case_id,
            "contract": None,
            "error": _reason(error),
            "narrative_meter": None,
            "model_calls": calls,
        }
    else:
        result = {
            "case_id": case_id,
            "contract": contract,
            "error": None,
            "narrative_meter": meter,
            "model_calls": calls,
        }
    if meter_path is not None:
        finished = result["contract"]
        narrative = result["narrative_meter"]
        record_case_meter(
            meter_path,
            case_id=result["case_id"],
            route=finished["routing"] if finished is not None else "not_built",
            started_at=started_at,
            latency_ms=round((time.perf_counter() - started) * 1000),
            model_calls=len(calls)
            + (0 if narrative is None else narrative["model_calls"]),
            input_tokens=sum(call["input_tokens"] or 0 for call in calls),
            output_tokens=sum(call["output_tokens"] or 0 for call in calls),
            tool_attempts=tally["tool_attempts"],
            retry_count=tally["retry_count"],
        )
    return result


def load_contract_results(
    base_url: str,
    data_dir: str | Path,
    writer: ProseWriter | None = None,
    model: ModelClient | None = None,
    *,
    meter_path: Path | None = None,
) -> list[ContractResult]:
    """Return one result per case in the bank case list, in bank order.

    A case that cannot be built has a null contract and the reason, and the
    remaining cases still run. The reason is one of this application's own
    messages or an exception class name, never text from a payload or document.
    When meter_path is set, the file is replaced and each case appends one line.
    A case list that cannot be read leaves the previous meter file alone.

    writer, when given, may reword each narrative; see src/narrative.py. Each
    built case carries its narrative meter (path, latency, model calls). model,
    when given, may answer the hybrid's questions, and each result lists the calls
    made for its case. The meter line records every model call made for the case
    (the hybrid's and the narrative writer's); token counts stay 0 because this
    meter does not count tokens.
    """
    data_dir = Path(data_dir)
    plans = contract_case_plans(base_url, data_dir)
    _prepare_meter_file(meter_path)
    return [
        build_contract_result(
            plan, base_url, data_dir, writer, model, meter_path=meter_path
        )
        for plan in plans
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
    for a complete one. One meter line per case is written to reports/meters.jsonl.

    MODEL_PROVIDER and its settings, when set, add a qualified model's answers
    (ADR-003; see src/model_clients.py). A model that cannot be used stops the run
    before any case is read, rather than running without it.
    """
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
    data_dir = sys.argv[2] if len(sys.argv) > 2 else "data/dev"
    try:
        model = model_from_env(os.environ)
    except ModelSetupError as error:
        sys.stderr.write(f"the model cannot be used: {error}\n")
        raise SystemExit(1) from None
    try:
        results = load_contract_results(
            base_url,
            data_dir,
            model=model,
            meter_path=Path("reports") / "meters.jsonl",
        )
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


def _prepare_meter_file(meter_path: Path | None) -> None:
    """Replace any previous run so this run owns every line in the file."""
    if meter_path is None:
        return
    meter_path.parent.mkdir(parents=True, exist_ok=True)
    meter_path.write_text("", encoding="utf-8")


def _contract_record(
    record: WorkingRecord,
    base_url: str,
    data_dir: Path,
    documents: list[str],
    writer: ProseWriter | None,
    model: ModelClient | None,
    calls: list[ModelCall],
    tally: dict[str, int],
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
    transactions, transactions_text = _transactions(base_url, record["case_id"], tally)
    enriched = build_transaction(record, transactions)
    merchant, private_token = _merchant(base_url, record["case_id"], tally)
    enriched = build_merchant(enriched, merchant)
    # The drafting and the output guard use the same known values, so a sentence holding
    # one is cited by its Source ID line instead of being quoted and then refused.
    known = [private_token, _customer_reference(intake_text)]
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
            model=model,
            model_calls=calls,
            known_values=known,
        )
    except ContractError as error:
        raise ContractRecordError from error
    try:
        guard(contract, known=known)
    except RestrictedValueError as error:
        raise ContractRecordError(str(error)) from None
    return contract, meter


def _transactions(
    base_url: str, case_id: str, tally: dict[str, int]
) -> tuple[TransactionTool, str]:
    """The transactions tool body, validated, and its text with sorted keys.

    The sorted text is the form the evaluator quotes tool bodies from.
    """
    raw = _read_tool(base_url, case_id, "transactions", tally)
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


def _merchant(
    base_url: str, case_id: str, tally: dict[str, int]
) -> tuple[MerchantTool, str]:
    """The merchant tool body, and its private token for the restricted-value guard.

    The private token is never copied into the merchant record.
    """
    try:
        payload = MerchantToolPayload.model_validate_json(
            _read_tool(base_url, case_id, "merchant", tally)
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


def _read_tool(base_url: str, case_id: str, tool: str, tally: dict[str, int]) -> bytes:
    """One observed tool read. Any failure is an error, never an empty result."""
    tally["tool_attempts"] += 1
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
