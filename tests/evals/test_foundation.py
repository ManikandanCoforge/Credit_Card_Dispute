"""The suite loader and the statistics must fail loudly on impossible input."""

from __future__ import annotations

import json

import pytest

from evals.dataset import SuiteError, format_errors, load_dataset, load_gold, load_suite
from evals.stats import proportion, wilson_interval


def test_suite_resolves_paths_against_repo_root(tmp_path):
    path = tmp_path / "suite.json"
    path.write_text(
        json.dumps({"name": "dev", "data": "data/dev", "gold": "feedback/dev_gold.json"})
    )
    suite = load_suite(path)
    assert suite["name"] == "dev"
    assert suite["data"].name == "dev"
    assert suite["gold"].name == "dev_gold.json"
    assert suite["metrics"] == []
    assert suite["gates"] == {}


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "x", "data": "d"},
        {"name": "", "data": "d", "gold": "g"},
        {"name": "x", "data": "d", "gold": "g", "extra": 1},
        {"name": "x", "data": "d", "gold": "g", "metrics": "pii"},
        {"name": "x", "data": "d", "gold": "g", "gates": {"pii": "high"}},
    ],
)
def test_suite_rejects_bad_shapes(tmp_path, payload):
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(SuiteError):
        load_suite(path)


def test_dataset_and_gold_reject_unknown_json(tmp_path):
    (tmp_path / "dataset.json").write_text("{")
    with pytest.raises(SuiteError):
        load_dataset(tmp_path)
    bad_gold = tmp_path / "gold.json"
    bad_gold.write_text("[]")
    with pytest.raises(SuiteError):
        load_gold(bad_gold)


def test_format_errors_names_every_structural_problem():
    dataset = {"cases": [{"case_id": "A"}, {"case_id": "B"}]}
    results = [
        {"case_id": "A", "contract": {}},
        {"case_id": "A", "contract": {}},
        {"case_id": "C", "contract": None},
    ]
    errors = format_errors(dataset, results)
    assert "duplicate result: A" in errors
    assert "missing result: B" in errors
    assert "unexpected result: C" in errors


def test_wilson_interval_brackets_the_rate_and_handles_extremes():
    low, high = wilson_interval(9, 12)
    assert low < 0.75 < high
    assert proportion(0, 0) is None
    with pytest.raises(ValueError):
        wilson_interval(0, 0)
    with pytest.raises(ValueError):
        proportion(2, 1)
    assert wilson_interval(0, 10)[0] == 0.0
    assert wilson_interval(10, 10)[1] == 1.0
