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
      a retryable failure is tried again, up to three attempts in all
    assemble_draft: the rules, with a configured model's two closed questions
      (ADR-003), then the narrative (template, or a configured writer)

Both tool reads go through the mock service, which audits each attempt. A
retryable failure (a dropped connection, or a 503 marked retryable) is tried
again with src/resilience.py, one breaker per tool for the whole run. Any other
failed read stops the case. A transaction service that stays unavailable is not
an empty history: the case is drafted for manual_review with amount and currency
null. A merchant service that stays unavailable stops the case. A stopped case
does not stop the others: load_contract_results keeps going and reports the
reason for each case it could not build.
"""

import json
import os
import re
import sys
import time
from collections.abc import Callable
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
    BankUnavailable,
    CaseListError,
    load_cases,
    read_body,
    records_from_case_list,
)
from src.meters import MeterLeak, record_case_meter
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
from src.resilience import (
    CircuitBreaker,
    DependencyUnavailable,
    TransientFailure,
    call_with_backoff,
)
from src.untrusted import RestrictedValueError, guard

_TOOLS = ("transactions", "merchant")
_MERCHANT_UNAVAILABLE = "the merchant service was unavailable"
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
    """One case's contract, its reason when it could not be built, and its meter.

    meter_error names the error that refused this case's meter line, or is None.
    A refused line never stops the run and never discards the case's result.
    """

    case_id: str
    contract: Contract | None
    error: str | None
    narrative_meter: NarrativeMeter | None
    model_calls: list[ModelCall]
    meter_error: str | None


class CasePlan(TypedDict):
    """One case's working record and the evidence the case list names for it."""

    record: WorkingRecord
    documents: list[str]


class ToolRetry:
    """How one run retries the two tool reads: a breaker per tool, and the wait between tries.

    A run keeps one ToolRetry for all its cases, so each breaker counts the complaints
    in a row that used every attempt. sleep is None for time.sleep; a test passes its own.
    tool_attempts and retry_count are running totals over the whole run; a case's meter
    line records the difference across that case's build.
    """

    def __init__(self, sleep: Callable[[float], None] | None = None) -> None:
        self.breakers = {tool: CircuitBreaker() for tool in _TOOLS}
        self.sleep = sleep
        self.tool_attempts = 0
        self.retry_count = 0


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
    retry: ToolRetry | None = None,
    model: ModelClient | None = None,
    *,
    meter_path: Path | None = None,
) -> ContractResult:
    """Build one case's contract from the bank and the dataset, or report the reason.

    The reason is one of this application's own messages or an exception class
    name, never text from a payload or document. writer, when given, may reword the
    narrative; see src/narrative.py. retry is the run's ToolRetry; without one, this
    case gets its own. model, when given, may answer the hybrid's two closed
    questions (ADR-003); its calls are kept even when the case is not built, because
    they were still made.

    When meter_path is set, one meter line is appended for this case after it
    finishes, including a case that stops. The line counts the tool attempts and
    the retries this case made. A line that would carry a restricted value is
    refused: the case keeps its result and meter_error names "MeterLeak", so one
    refused line never stops the run.
    """
    started_at = datetime.now(UTC)
    started = time.perf_counter()
    case_id = plan["record"]["case_id"]
    calls: list[ModelCall] = []
    retry = ToolRetry() if retry is None else retry
    attempts_before = retry.tool_attempts
    retries_before = retry.retry_count
    try:
        contract, meter = _contract_record(
            plan["record"],
            base_url,
            Path(data_dir),
            plan["documents"],
            writer,
            retry,
            model,
            calls,
        )
    except ContractRecordError as error:
        result: ContractResult = {
            "case_id": case_id,
            "contract": None,
            "error": _reason(error),
            "narrative_meter": None,
            "model_calls": calls,
            "meter_error": None,
        }
    else:
        result = {
            "case_id": case_id,
            "contract": contract,
            "error": None,
            "narrative_meter": meter,
            "model_calls": calls,
            "meter_error": None,
        }
    if meter_path is not None:
        finished = result["contract"]
        narrative = result["narrative_meter"]
        try:
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
                tool_attempts=retry.tool_attempts - attempts_before,
                retry_count=retry.retry_count - retries_before,
            )
        except MeterLeak:
            result["meter_error"] = "MeterLeak"
    return result


def load_contract_results(
    base_url: str,
    data_dir: str | Path,
    writer: ProseWriter | None = None,
    retry: ToolRetry | None = None,
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
    built case carries its narrative meter (path, latency, model calls). Every case
    shares one ToolRetry, retry or a new one. model, when given, may answer the
    hybrid's questions, and each result lists the calls made for its case.

    The meter line records every model call made for the case (the hybrid's and the
    narrative writer's) and sums their input and output tokens, counting a call that
    reported no count as 0. A meter line that would carry a restricted value is
    skipped for that case, and its result carries "MeterLeak" in meter_error.
    """
    data_dir = Path(data_dir)
    plans = contract_case_plans(base_url, data_dir)
    _prepare_meter_file(meter_path)
    shared = ToolRetry() if retry is None else retry
    return [
        build_contract_result(
            plan,
            base_url,
            data_dir,
            writer,
            retry=shared,
            model=model,
            meter_path=meter_path,
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
    retry: ToolRetry,
    model: ModelClient | None,
    calls: list[ModelCall],
) -> tuple[Contract, NarrativeMeter]:
    """Read the evidence and the tools for one case, then assemble its contract.

    documents is the evidence the case list names for this case. Besides the
    intake and the attachment, a listed customer statement, such as a follow-up
    email, is read and passed on. Any other listed source is refused rather than
    ignored, so evidence can never be silently left out of the draft.

    A transaction service that is still unavailable after its attempts leaves the
    record with no transactions and no tool text; assemble_draft then routes the
    case to manual_review with amount and currency null.
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
    transactions = _transactions(base_url, record["case_id"], retry)
    if transactions is None:
        enriched: WorkingRecord = {**record, "transactions": []}
        transactions_text = None
    else:
        tool, transactions_text = transactions
        enriched = build_transaction(record, tool)
    merchant, private_token = _merchant(base_url, record["case_id"], retry)
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
    base_url: str, case_id: str, retry: ToolRetry
) -> tuple[TransactionTool, str] | None:
    """The transactions tool body, validated, and its text with sorted keys.

    The sorted text is the form the evaluator quotes tool bodies from. None means the
    service did not answer within its attempts, or its breaker is open: the history is
    unknown, which is never the same as an empty one.
    """
    try:
        raw = _read_tool(base_url, case_id, "transactions", retry)
    except DependencyUnavailable:
        return None
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


def _merchant(base_url: str, case_id: str, retry: ToolRetry) -> tuple[MerchantTool, str]:
    """The merchant tool body, and its private token for the restricted-value guard.

    The private token is never copied into the merchant record. A merchant service
    that does not answer within its attempts stops the case: the procedure says to
    retrieve merchant context, and gives no way to draft without it.
    """
    try:
        raw = _read_tool(base_url, case_id, "merchant", retry)
    except DependencyUnavailable:
        raise ContractRecordError(_MERCHANT_UNAVAILABLE) from None
    try:
        payload = MerchantToolPayload.model_validate_json(raw)
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


def _read_tool(base_url: str, case_id: str, tool: str, retry: ToolRetry) -> bytes:
    """One tool read, tried again after a retryable failure, up to three attempts in all.

    Every attempt is a separate observed request and counts toward the run's
    tool_attempts; each try after the first counts toward retry_count. Any other
    failure stops the case at once: it is an error, never an empty result.
    DependencyUnavailable, when every attempt failed or the tool's breaker is open,
    is left to the caller.
    """
    path = f"/v1/cases/{quote(case_id, safe='')}/{tool}"
    attempts = 0

    def attempt() -> bytes:
        nonlocal attempts
        attempts += 1
        retry.tool_attempts += 1
        if attempts > 1:
            retry.retry_count += 1
        try:
            return read_body(base_url, path)
        except BankUnavailable as error:
            raise TransientFailure from error

    try:
        return call_with_backoff(attempt, retry.breakers[tool], sleep=retry.sleep)
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
