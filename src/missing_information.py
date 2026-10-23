"""Keep the absent intake lines that the classification still requires."""

from src.models import WorkingRecord

_REQUIRED = {
    "unauthorized": ("authorization_confirmation",),
    "duplicate_charge": (),
    "service_not_received": ("promised_service_date", "purchase_receipt"),
    "ambiguous": (),
    "unsupported": (),
}


def narrow_absent_fields(record: WorkingRecord, classification: str | None) -> WorkingRecord:
    """Return the record with missing_information for a known classification.

    An unknown classification, or a record that has not been scanned, comes
    back without that field.
    """
    required = _REQUIRED.get(classification or "")
    if required is None or "absent_fields" not in record:
        return record
    missing = [field for field in record["absent_fields"] if field in required]
    return {**record, "missing_information": missing}
