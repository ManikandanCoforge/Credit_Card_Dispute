import pytest

from src.missing_information import narrow_absent_fields


def test_unauthorized_keeps_only_authorization_confirmation():
    record = _record(
        [
            "authorization_confirmation",
            "promised_service_date",
            "purchase_receipt",
        ]
    )

    result = narrow_absent_fields(record, "unauthorized")

    assert result["missing_information"] == ["authorization_confirmation"]
    assert result["absent_fields"] == record["absent_fields"]


def test_service_not_received_keeps_service_fields_in_scan_order():
    record = _record(
        [
            "authorization_confirmation",
            "purchase_receipt",
            "promised_service_date",
        ]
    )

    result = narrow_absent_fields(record, "service_not_received")

    assert result["missing_information"] == [
        "purchase_receipt",
        "promised_service_date",
    ]


@pytest.mark.parametrize(
    "classification",
    ["duplicate_charge", "ambiguous", "unsupported"],
)
def test_classifications_without_required_lines_keep_nothing(classification):
    record = _record(
        [
            "authorization_confirmation",
            "promised_service_date",
            "purchase_receipt",
        ]
    )

    result = narrow_absent_fields(record, classification)

    assert result["missing_information"] == []


def test_unauthorized_with_nothing_absent_records_an_empty_list():
    result = narrow_absent_fields(_record([]), "unauthorized")

    assert result["missing_information"] == []


def test_service_not_received_keeps_only_the_field_on_the_scan():
    result = narrow_absent_fields(_record(["purchase_receipt"]), "service_not_received")

    assert result["missing_information"] == ["purchase_receipt"]


@pytest.mark.parametrize(
    "classification",
    [None, "", "provisional unauthorized"],
)
def test_an_unknown_classification_leaves_missing_information_unset(classification):
    record = _record(["authorization_confirmation"])

    result = narrow_absent_fields(record, classification)

    assert result == record
    assert "missing_information" not in result


def test_narrowing_does_not_change_the_record_it_was_given():
    record = _record(["authorization_confirmation"])

    narrow_absent_fields(record, "unauthorized")

    assert "missing_information" not in record


def test_a_record_without_a_scan_is_left_unchanged():
    record = {
        "case_id": "CARD-D04",
        "intake": {"authorization": "not supplied"},
        "policy": {
            "version_id": "CARD-POLICY-V2",
            "procedure_id": "CARD-PROCEDURE-01",
        },
    }

    result = narrow_absent_fields(record, "unauthorized")

    assert result == record
    assert "missing_information" not in result


def _record(absent_fields):
    return {
        "case_id": "CARD-D04",
        "intake": {"authorization": "not supplied"},
        "policy": {
            "version_id": "CARD-POLICY-V2",
            "procedure_id": "CARD-PROCEDURE-01",
        },
        "absent_fields": absent_fields,
    }
