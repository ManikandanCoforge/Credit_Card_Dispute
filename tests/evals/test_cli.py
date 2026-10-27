"""The command writes both reports and returns the documented exit codes."""

from __future__ import annotations

import json

from evals.cli import main
from tests.evals.support import GOLD

FIXTURE_GOLD = {
    "HID-01": dict(GOLD, routing=["request_information"], classification=["unauthorized"])
}


def test_dev_suite_writes_both_reports_and_matches_its_exit_code(tmp_path):
    base = tmp_path / "eval-dev"
    code = main(["--suite", "evals/suites/dev.json", "--out", str(base)])
    payload = json.loads(base.with_suffix(".json").read_text(encoding="utf-8"))
    assert payload["cases"]["total"] == 12
    assert payload["suite"] == "dev"
    assert payload["checks"]
    expected = 0 if all(row["passed"] for row in payload["case_results"]) else 1
    assert code == expected
    assert base.with_suffix(".md").read_text(encoding="utf-8").startswith("# Evaluation report")



def test_report_only_returns_zero_on_the_same_failures(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    dataset = {
        "name": "fixture",
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
        "sources": {"HID-01-INTAKE": "I do not recognize this charge."},
    }
    (data / "dataset.json").write_text(json.dumps(dataset), encoding="utf-8")
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps(FIXTURE_GOLD), encoding="utf-8")
    suite = tmp_path / "suite.json"
    suite.write_text(
        json.dumps(
            {
                "name": "injected",
                "data": str(data),
                "gold": str(gold),
                "metrics": ["pii"],
            }
        ),
        encoding="utf-8",
    )
    base = tmp_path / "eval-injected"
    code = main(["--suite", str(suite), "--out", str(base), "--report-only"])
    assert code == 0
    assert base.with_suffix(".md").exists()
