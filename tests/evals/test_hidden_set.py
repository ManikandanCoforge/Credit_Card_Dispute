"""The hidden-set path carries whatever identifiers the injected dataset names."""

from __future__ import annotations

import json
from pathlib import Path

from evals.runner import run_evaluation


def _fixture(root: Path) -> tuple[Path, Path]:
    data = root / "data"
    data.mkdir()
    dataset = {
        "name": "injected-fixture",
        "allow_write": False,
        "cases": [
            {
                "case_id": "HID-01",
                "intake_source": "HID-01-INTAKE",
                "documents": ["HID-01-INTAKE"],
                "logical_key": "hid-1",
                "tools": {},
                "faults": {},
            }
        ],
        "sources": {"HID-01-INTAKE": "I do not recognize this charge. Please check it."},
    }
    (data / "dataset.json").write_text(json.dumps(dataset))
    gold = root / "gold.json"
    gold.write_text(
        json.dumps(
            {
                "HID-01": {
                    "classification": ["unauthorized"],
                    "routing": ["request_information"],
                    "policy_ids": [],
                    "facts": {},
                    "missing_information": ["amount"],
                    "deadline": None,
                    "evidence_groups": [["HID-01-INTAKE"]],
                    "restricted_values": [],
                }
            }
        )
    )
    return data, gold


def test_an_injected_dataset_keeps_its_own_case_ids(tmp_path):
    data, gold = _fixture(tmp_path)
    run = run_evaluation(data, gold, "injected")
    assert [case.case_id for case in run.cases] == ["HID-01"]
    assert run.set_name == "injected"
    assert run.format_errors == ()
