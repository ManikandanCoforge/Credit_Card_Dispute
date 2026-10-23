"""Turn a complaint intake into JSON, then add the policy version and procedure."""

from datetime import date
from pathlib import Path
from typing import TypedDict

from src.models import Case, Intake, Policy, WorkingRecord


class _Complaint(TypedDict):
    case_id: str
    intake: Intake


class _PolicyVersion(TypedDict):
    source_id: str
    start: date
    end: date
    procedure_id: str | None


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
    and the procedure that version names. When the reported date is missing,
    or it matches no version or more than one, both policy ids are left empty.
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
    # A missing date, no window, or two windows is not a choice. The later file does not win.
    if len(chosen) != 1:
        return {"version_id": None, "procedure_id": None}
    match = chosen[0]
    return {
        "version_id": match["source_id"],
        "procedure_id": match["procedure_id"],
    }


def _policy_versions(policies_dir: Path) -> list[_PolicyVersion]:
    versions: list[_PolicyVersion] = []
    for path in policies_dir.glob("*.md"):
        text = path.read_text()
        start = _day(_field(text, "Effective from", word=True))
        end = _day(_field(text, "Effective through", word=True))
        source_id = _field(text, "Source ID", word=True)
        if source_id is None or source_id != path.stem or start is None or end is None or end < start:
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
    reported = _day(_field(text, "Reported date", word=True))
    statement = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
        and not line.strip().startswith("#")
        and not any(line.strip().startswith(f"{label}:") for label in _LABELS)
    ]
    return {
        "source_id": _field(text, "Source ID", word=True),
        "statement": " ".join(statement) or None,
        "reported_date": None if reported is None else reported.isoformat(),
        "transaction_id": _field(text, "Transaction ID"),
        "authorization": _field(text, "Authorization"),
        "promised_service_date": _field(text, "Promised service date"),
        "purchase_receipt": _field(text, "Purchase receipt"),
        "submission_reference": _field(text, "Submission reference"),
    }, reported


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


def _field(text: str, label: str, *, word: bool = False) -> str | None:
    """Read one `Label: value` line.

    word=True keeps a single token, such as a source id.
    The default keeps the text, including "not supplied".
    Zero lines, two lines, or a blank value means the field is missing.
    """
    prefix = f"{label}: "
    found: list[str] = [
        line.strip()[len(prefix) :]
        for line in text.splitlines()
        if line.strip().startswith(prefix)
    ]
    # One answer only. A repeated label is a conflict, not a choice.
    if len(found) != 1 or not found[0]:
        return None
    value = found[0]
    # A source id or a date is one word. "not supplied" is neither.
    if word and " " in value:
        return None
    return value


def _day(value: str | None) -> date | None:
    """Keep a token only when it is a real YYYY-MM-DD day."""
    if value is None:
        return None
    # Reject 2026-02-31 and anything that is not exactly YYYY-MM-DD.
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    if parsed.isoformat() != value:
        return None
    return parsed
