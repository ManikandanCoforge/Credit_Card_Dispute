"""Turn a complaint intake into JSON, then add the policy version and procedure."""

from datetime import date
from pathlib import Path

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


def build_complaint_records(cases, data_dir):
    """Build one working record per complaint.

    A working record is the intake turned into JSON, plus the policy version
    and the procedure that version names. When the reported date is missing,
    or it matches no version or more than one, both policy ids are left empty.
    Transaction and merchant details are added in a later step.
    """
    data_dir = Path(data_dir)
    versions = _policy_versions(data_dir / "policies")
    records = []
    for case in cases:
        document = data_dir / "documents" / f"{case['intake_source']}.md"
        try:
            text = document.read_text()
        except OSError:
            text = ""
        record, reported = _complaint(case, text)
        record["policy"] = _policy(reported, versions)
        records.append(record)
    return records


def build_complaint_record(case, data_dir):
    """Build the working record for one complaint.

    This is the same record one item of build_complaint_records would hold.
    """
    return build_complaint_records([case], data_dir)[0]


def _complaint(case, text):
    intake, reported = _intake(text)
    return {"case_id": case["case_id"], "intake": intake}, reported


def _policy(reported, versions):
    chosen = [
        version
        for version in versions
        if reported is not None and version["start"] <= reported <= version["end"]
    ]
    # A missing date, no window, or two windows is not a choice. The later file does not win.
    if len(chosen) != 1:
        return {"version_id": None, "procedure_id": None}
    chosen = chosen[0]
    return {
        "version_id": chosen["source_id"],
        "procedure_id": chosen["procedure_id"],
    }


def _policy_versions(policies_dir):
    versions = []
    for path in policies_dir.glob("*.md"):
        text = path.read_text()
        start = _field(text, "Effective from", kind="date")
        end = _field(text, "Effective through", kind="date")
        source_id = _field(text, "Source ID", kind="word")
        if source_id != path.stem or start is None or end is None or end < start:
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


def _intake(text):
    reported = _field(text, "Reported date", kind="date")
    statement = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
        and not line.strip().startswith("#")
        and not any(line.strip().startswith(f"{label}:") for label in _LABELS)
    ]
    return {
        "source_id": _field(text, "Source ID", kind="word"),
        "statement": " ".join(statement) or None,
        "reported_date": None if reported is None else reported.isoformat(),
        "transaction_id": _field(text, "Transaction ID"),
        "authorization": _field(text, "Authorization"),
        "promised_service_date": _field(text, "Promised service date"),
        "purchase_receipt": _field(text, "Purchase receipt"),
        "submission_reference": _field(text, "Submission reference"),
    }, reported


def _procedure(text):
    marker = "Follow the common procedures in "
    found = []
    for line in text.splitlines():
        if marker not in line:
            continue
        token = line.split(marker, 1)[1].split(".", 1)[0].strip()
        if token and " " not in token:
            found.append(token)
    if len(found) == 1:
        return found[0]
    return None


def _field(text, label, *, kind="value"):
    """Read one `Label: value` line.

    kind="value" keeps the text, including "not supplied".
    kind="word" keeps a single token, such as a source id.
    kind="date" keeps that token only when it is a real YYYY-MM-DD day.
    Zero lines, two lines, or a blank value means the field is missing.
    """
    prefix = f"{label}: "
    found = [
        line.strip()[len(prefix) :]
        for line in text.splitlines()
        if line.strip().startswith(prefix)
    ]
    # One answer only. A repeated label is a conflict, not a choice.
    if len(found) != 1 or not found[0]:
        return None
    value = found[0]
    if kind == "value":
        return value
    # A source id or a date is one word. "not supplied" is neither.
    if " " in value:
        return None
    if kind == "word":
        return value
    # Reject 2026-02-31 and anything that is not exactly YYYY-MM-DD.
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    if parsed.isoformat() != value:
        return None
    return parsed
