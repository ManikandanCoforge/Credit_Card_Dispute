"""Turn a complaint intake into JSON, then add the policy version and procedure."""

from datetime import date
from pathlib import Path
from typing import TypedDict

from src.models import (
    Case,
    Intake,
    Merchant,
    MerchantTool,
    Policy,
    Transaction,
    TransactionTool,
    WorkingRecord,
)


class _Complaint(TypedDict):
    case_id: str
    intake: Intake


class _PolicyVersion(TypedDict):
    source_id: str
    start: date
    end: date
    procedure_id: str | None


# A missing, blank, or conflicting label is these words. It is never an empty value.
_NOT_SUPPLIED = "not supplied"

# Customer reference is listed so it stays out of the statement. It is not copied.
_LABELS = (
    "Source ID",
    "Reported date",
    "Transaction ID",
    "Customer reference",
    "Authorization",
    "Promised service date",
    "Purchase receipt",
    "Submission reference",
)


def build_complaint_records(cases: list[Case], data_dir: str | Path) -> list[WorkingRecord]:
    """Build one working record per complaint.

    A working record is the intake turned into JSON, plus the policy version
    and the procedure that version names. A missing intake field is the words
    "not supplied". When that is the reported date, or the date matches no
    version or more than one, both policy ids are left empty.
    missing_information lists each intake line whose value is exactly "not supplied".
    routing is request_information when that list has any line.
    Transaction and merchant details are added in a later step.
    """
    data_dir = Path(data_dir)
    versions = _policy_versions(data_dir / "policies")
    records: list[WorkingRecord] = []
    for case in cases:
        document = data_dir / "documents" / f"{case['intake_source']}.md"
        try:
            text = document.read_text()
        except OSError:
            text = ""
        complaint, reported = _complaint(case, text)
        missing_information = _missing_information(complaint["intake"])
        records.append(
            {
                "case_id": complaint["case_id"],
                "intake": complaint["intake"],
                "policy": _policy(reported, versions),
                "missing_information": missing_information,
                "routing": "request_information" if missing_information else None,
            }
        )
    return records


def build_transaction(record: WorkingRecord, tool_body: TransactionTool) -> WorkingRecord:
    """Return the working record with one transaction per charge in the tool body.

    The input record is left unchanged. The tool body's source id is not copied.
    """
    charges: list[Transaction] = [
        {
            "transaction_id": charge["transaction_id"],
            "amount": charge["amount"],
            "currency": charge["currency"],
            "merchant_id": charge["merchant_id"],
            "posted_date": charge["posted_date"],
        }
        for charge in tool_body["transactions"]
    ]
    return {**record, "transactions": charges}


def build_merchant(record: WorkingRecord, tool_body: MerchantTool) -> WorkingRecord:
    """Return the working record with the merchant from the tool body.

    The input record is left unchanged. The tool body's source id and private
    token are not copied. The note is stored as supplied.
    """
    merchant: Merchant = {
        "merchant_id": tool_body["merchant_id"],
        "display_name": tool_body["display_name"],
        "note": tool_body["note"],
    }
    return {**record, "merchant": merchant}


def build_complaint_record(case: Case, data_dir: str | Path) -> WorkingRecord:
    """Build the working record for one complaint.

    This is the same record one item of build_complaint_records would hold.
    """
    return build_complaint_records([case], data_dir)[0]


def _missing_information(intake: Intake) -> list[str]:
    absent: list[str] = []
    if intake["authorization"] == "not supplied":
        absent.append("authorization_confirmation")
    if intake["promised_service_date"] == "not supplied":
        absent.append("promised_service_date")
    if intake["purchase_receipt"] == "not supplied":
        absent.append("purchase_receipt")
    return absent


def _complaint(case: Case, text: str) -> tuple[_Complaint, date | None]:
    intake, reported = _intake(text)
    return {"case_id": case["case_id"], "intake": intake}, reported


def _policy(reported: date | None, versions: list[_PolicyVersion]) -> Policy:
    chosen = [
        version
        for version in versions
        if reported is not None and version["start"] <= reported <= version["end"]
    ]
    if len(chosen) != 1:
        # No version, or more than one, covers the date. The procedure the covering
        # versions name, or with none every version names, still applies, so the case
        # can be drafted for a person under it.
        procedures = {version["procedure_id"] for version in chosen or versions}
        procedure_id = procedures.pop() if len(procedures) == 1 else None
        return {"version_id": None, "procedure_id": procedure_id}
    match = chosen[0]
    return {
        "version_id": match["source_id"],
        "procedure_id": match["procedure_id"],
    }


def _policy_versions(policies_dir: Path) -> list[_PolicyVersion]:
    versions: list[_PolicyVersion] = []
    for path in policies_dir.glob("*.md"):
        text = path.read_text()
        start = _day(_field(text, "Effective from"))
        end = _day(_field(text, "Effective through"))
        source_id = _field(text, "Source ID")
        if (
            source_id == _NOT_SUPPLIED
            or source_id != path.stem
            or start is None
            or end is None
            or end < start
        ):
            continue
        versions.append(
            {
                "source_id": source_id,
                "start": start,
                "end": end,
                "procedure_id": _procedure(text),
            }
        )
    return versions


def _intake(text: str) -> tuple[Intake, date | None]:
    reported_date = _field(text, "Reported date")
    return {
        "source_id": _field(text, "Source ID"),
        "statement": _statement(text),
        "reported_date": reported_date,
        "transaction_id": _field(text, "Transaction ID"),
        "authorization": _field(text, "Authorization"),
        "promised_service_date": _field(text, "Promised service date"),
        "purchase_receipt": _field(text, "Purchase receipt"),
        "submission_reference": _field(text, "Submission reference"),
    }, _day(reported_date)


def _statement(text: str) -> str:
    """The customer's free text before the form fields.

    Text after the form fields, such as the delivery note on a redelivered complaint, is
    not the customer's account. Joined on, it made a statement the intake never says in
    one place, so the draft could not quote it. It stays in the intake, which every
    detector still reads, and is the statement only when nothing precedes the form.
    """
    before: list[str] = []
    after: list[str] = []
    in_form = False
    for line in text.splitlines():
        stripped = line.strip()
        label = next((label for label in _LABELS if stripped.startswith(f"{label}:")), None)
        if label is not None:
            in_form = in_form or label != "Source ID"
        elif stripped and not stripped.startswith("#"):
            (after if in_form else before).append(stripped)
    return " ".join(before or after) or _NOT_SUPPLIED


def _procedure(text: str) -> str | None:
    marker = "Follow the common procedures in "
    found: list[str] = []
    for line in text.splitlines():
        if marker not in line:
            continue
        token = line.split(marker, 1)[1].split(".", 1)[0].strip()
        if token and " " not in token:
            found.append(token)
    if len(found) == 1:
        return found[0]
    return None


def _field(text: str, label: str) -> str:
    """Read one `Label: value` line.

    Zero lines, two lines, or a blank value means the field is not supplied.
    """
    prefix = f"{label}:"
    found = [
        line.strip()[len(prefix) :].strip()
        for line in text.splitlines()
        if line.strip().startswith(prefix)
    ]
    if len(found) != 1 or not found[0]:
        return _NOT_SUPPLIED
    return found[0]


def _day(value: str) -> date | None:
    """Parse a YYYY-MM-DD day. A field that is not supplied, or not an ISO date, is not a day.

    An intake that writes "October 3, 2026" then selects no policy version, so only that
    case stops, and a policy with an unreadable window is skipped like one with none.
    Raising here would stop every case in the case list.
    """
    if value == _NOT_SUPPLIED:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
