from pathlib import Path

import pytest

from src.complaints import build_complaint_records

DEV = Path(__file__).resolve().parents[1] / "data" / "dev"


def test_card_d01_records_policy_version_2():
    result = build_complaint_records(
        [{"case_id": "CARD-D01", "intake_source": "CARD-D01-INTAKE"}],
        DEV,
    )

    assert result == [
        {
            "case_id": "CARD-D01",
            "intake": {
                "source_id": "CARD-D01-INTAKE",
                "statement": (
                    "I found a card purchase at Morrow Supplies for 117 crowns. "
                    "I do not recognize it and need help checking it."
                ),
                "reported_date": "2026-10-01",
                "transaction_id": "TX-D01",
                "authorization": "denied",
                "promised_service_date": "2026-08-20",
                "purchase_receipt": "attached",
                "submission_reference": "dispute-d01",
            },
            "policy": {
                "version_id": "CARD-POLICY-V2",
                "procedure_id": "CARD-PROCEDURE-01",
            },
        }
    ]


def test_card_d11_records_policy_version_1():
    result = build_complaint_records(
        [{"case_id": "CARD-D11", "intake_source": "CARD-D11-INTAKE"}],
        DEV,
    )

    assert result == [
        {
            "case_id": "CARD-D11",
            "intake": {
                "source_id": "CARD-D11-INTAKE",
                "statement": (
                    "I found a card purchase at Morrow Supplies for 287 crowns. "
                    "I do not recognize it and need help checking it."
                ),
                "reported_date": "2026-08-31",
                "transaction_id": "TX-D11",
                "authorization": "denied",
                "promised_service_date": "2026-08-20",
                "purchase_receipt": "attached",
                "submission_reference": "dispute-d11",
            },
            "policy": {
                "version_id": "CARD-POLICY-V1",
                "procedure_id": "CARD-PROCEDURE-01",
            },
        }
    ]


def test_window_ends_select_the_version_that_owns_them(tmp_path):
    cases = _dataset_with_intakes(
        tmp_path,
        [
            ("DAY-V1-START", "2026-01-01"),
            ("DAY-V1-END", "2026-08-31"),
            ("DAY-V2-START", "2026-09-01"),
            ("DAY-V2-END", "2026-12-31"),
        ],
    )

    result = build_complaint_records(cases, tmp_path)

    assert result == [
        _matched("DAY-V1-START", "2026-01-01", "CARD-POLICY-V1"),
        _matched("DAY-V1-END", "2026-08-31", "CARD-POLICY-V1"),
        _matched("DAY-V2-START", "2026-09-01", "CARD-POLICY-V2"),
        _matched("DAY-V2-END", "2026-12-31", "CARD-POLICY-V2"),
    ]


def test_records_follow_the_case_list_order():
    result = build_complaint_records(
        [
            {"case_id": "CARD-D11", "intake_source": "CARD-D11-INTAKE"},
            {"case_id": "CARD-D01", "intake_source": "CARD-D01-INTAKE"},
        ],
        DEV,
    )

    assert [record["case_id"] for record in result] == [
        "CARD-D11",
        "CARD-D01",
    ]


def test_unusable_policy_lines_do_not_change_the_matching_version(tmp_path):
    cases = _dataset_with_intakes(tmp_path, [("CARD-D01", "2026-10-01")])
    policies = tmp_path / "policies"
    (policies / "SKIP-SPACE.md").write_text("Effective from: not supplied\n")
    (policies / "SKIP-DAY.md").write_text("Effective from: 2026-02-31\n")
    (policies / "SKIP-COMPACT.md").write_text("Effective from: 20261001\n")
    (policies / "OLD-POLICY.md").write_text(
        "Source ID: OLD-POLICY\n"
        "Effective from: 2025-01-01\n"
        "Effective through: 2025-01-31\n"
        "This file names no procedure.\n"
    )

    result = build_complaint_records(cases, tmp_path)

    assert result[0]["policy"] == {
        "version_id": "CARD-POLICY-V2",
        "procedure_id": "CARD-PROCEDURE-01",
    }


def test_missing_intake_file_does_not_produce_a_record(tmp_path):
    _dataset_with_intakes(tmp_path, [])

    with pytest.raises(TypeError):
        build_complaint_records(
            [{"case_id": "MISSING", "intake_source": "MISSING-INTAKE"}],
            tmp_path,
        )


def test_builder_leaves_the_dataset_unchanged(tmp_path):
    cases = _dataset_with_intakes(tmp_path, [("CARD-D01", "2026-10-01")])
    before = _snapshot(tmp_path)

    build_complaint_records(cases, tmp_path)

    assert _snapshot(tmp_path) == before


def _dataset_with_intakes(tmp_path, intakes):
    policies = tmp_path / "policies"
    policies.mkdir()
    for policy in (DEV / "policies").glob("*.md"):
        (policies / policy.name).write_text(policy.read_text())
    documents = tmp_path / "documents"
    documents.mkdir()
    cases = []
    for case_id, reported_date in intakes:
        source = f"{case_id}-INTAKE"
        (documents / f"{source}.md").write_text(f"Reported date: {reported_date}\n")
        cases.append({"case_id": case_id, "intake_source": source})
    return cases


def _matched(case_id, reported_date, version_id):
    return {
        "case_id": case_id,
        "intake": {
            "source_id": None,
            "statement": None,
            "reported_date": reported_date,
            "transaction_id": None,
            "authorization": None,
            "promised_service_date": None,
            "purchase_receipt": None,
            "submission_reference": None,
        },
        "policy": {
            "version_id": version_id,
            "procedure_id": "CARD-PROCEDURE-01",
        },
    }


def _snapshot(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
