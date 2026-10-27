"""Error paths: every failure the suite can meet must fail loudly, not quietly.

These tests exist so the coverage gate includes `evals/`, not only `src/`. A
hidden-set run is exactly where a swallowed read error would look like a pass.
"""

from __future__ import annotations

import json
import runpy
import sqlite3
import subprocess
import sys
import types
from pathlib import Path

import pytest

from evals import mockbank, report, runner
from evals.dataset import (
    SuiteError,
    format_errors,
    load_dataset,
    load_gold,
    load_suite,
)
from evals.metrics import escalation, grounding, pii, run_metrics, tools
from tests.evals.support import (
    CONTRACT,
    GOLD,
    make_case,
    make_run,
    tool_event,
)

CASE = "CASE-1"


def test_module_entry_point_runs_the_cli(capsys):
    """`python -m evals` must execute main, not just import it."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sys, "argv", ["evals", "--help"])
        with pytest.raises(SystemExit) as raised:
            runpy.run_module("evals", run_name="__main__")
    assert raised.value.code == 0
    assert "Run the offline evaluation suite" in capsys.readouterr().out


def test_load_suite_rejects_a_missing_file(tmp_path):
    with pytest.raises(SuiteError, match="cannot read suite"):
        load_suite(tmp_path / "missing.json")


@pytest.mark.parametrize("text", ["{", "[]"])
def test_load_suite_rejects_bad_json_and_non_objects(tmp_path, text):
    path = tmp_path / "suite.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(SuiteError):
        load_suite(path)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"cases": [], "sources": {"a": "b"}},
        {"cases": [{"case_id": "A", "tools": {}, "documents": []}], "sources": {}},
        {"cases": [{"case_id": 1, "tools": {}, "documents": []}], "sources": {"a": "b"}},
        {"cases": [{"case_id": "A", "documents": []}], "sources": {"a": "b"}},
        {"cases": [{"case_id": "A", "tools": {}}], "sources": {"a": "b"}},
        {
            "cases": [
                {"case_id": "A", "tools": {}, "documents": []},
                {"case_id": "A", "tools": {}, "documents": []},
            ],
            "sources": {"a": "b"},
        },
        {"cases": [{"case_id": "A", "tools": {}, "documents": []}], "sources": {"a": 1}},
    ],
)
def test_load_dataset_rejects_every_unusable_shape(tmp_path, payload):
    data = tmp_path / "data"
    data.mkdir()
    (data / "dataset.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SuiteError):
        load_dataset(data)


def test_load_dataset_rejects_a_missing_file(tmp_path):
    with pytest.raises(SuiteError, match="cannot read dataset"):
        load_dataset(tmp_path / "missing")


def test_load_dataset_rejects_bad_json(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "dataset.json").write_text("{", encoding="utf-8")
    with pytest.raises(SuiteError):
        load_dataset(data)


def test_load_gold_rejects_a_missing_file(tmp_path):
    with pytest.raises(SuiteError, match="cannot read gold"):
        load_gold(tmp_path / "missing.json")


@pytest.mark.parametrize("text", ["{", "[]", '{"A": 1}'])
def test_load_gold_rejects_bad_json_and_non_object_entries(tmp_path, text):
    path = tmp_path / "gold.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(SuiteError):
        load_gold(path)


def test_format_errors_rejects_an_unreadable_result_and_contract():
    dataset = {"cases": [{"case_id": "A"}]}
    errors = format_errors(
        dataset,
        [
            {"contract": {}},
            {"case_id": "A", "contract": "not an object"},
        ],
    )
    assert "a result has no string case_id" in errors
    assert "contract is not an object: A" in errors


def test_run_metrics_rejects_an_unknown_name():
    with pytest.raises(ValueError, match="unknown metrics"):
        run_metrics(make_run(), ["pii.restricted_values"])


def test_escalation_handles_gold_without_a_list():
    run = make_run([make_case(gold=dict(GOLD, classification="unauthorized"))])
    checks = {check.metric: check for check in escalation.run(run)}
    assert checks["escalation.class_correct"].passed is False
    assert "no classification value" in checks["escalation.class_correct"].reason


def test_grounding_handles_citations_that_are_not_a_list():
    contract = {**CONTRACT, "citations": "not-a-list"}
    checks = {check.metric: check for check in grounding.run(make_run([make_case(contract=contract)]))}
    assert checks["grounding.citation_exact"].passed is False


def test_pii_accepts_a_string_restricted_value():
    gold = dict(GOLD, restricted_values="SYNTHETIC-PRIVATE-CASE-1")
    run = make_run(
        [make_case(gold=gold, contract={**CONTRACT, "narrative": "leak SYNTHETIC-PRIVATE-CASE-1"})]
    )
    checks = {check.metric: check for check in pii.run(run)}
    assert checks["pii.restricted_values"].passed is False


def test_pii_accepts_a_scalar_restricted_value():
    gold = dict(GOLD, restricted_values=424242)
    run = make_run([make_case(gold=gold, contract={**CONTRACT, "narrative": "amount 424242"})])
    checks = {check.metric: check for check in pii.run(run)}
    assert checks["pii.restricted_values"].passed is False


def test_tool_status_that_is_missing_is_named_unknown():
    result = {
        check.metric: check
        for check in tools.run(
            make_run(
                [
                    make_case(
                        audit=[
                            tool_event(CASE, "transactions", 1, None),
                            tool_event(CASE, "merchant", 1, 200),
                        ]
                    )
                ]
            )
        )
    }
    assert result["tools.required_reads"].passed is False
    assert "unknown" in result["tools.required_reads"].reason


def test_a_mock_that_exits_before_health_is_a_suite_error():
    process = subprocess.Popen(
        [sys.executable, "-c", "raise SystemExit(3)"],
        stderr=subprocess.PIPE,
        text=True,
    )
    process.wait(timeout=5)
    with pytest.raises(SuiteError, match="exited before it was healthy"):
        mockbank._wait_until_healthy("http://127.0.0.1:1", process)
    if process.stderr is not None:
        process.stderr.close()


def test_a_health_endpoint_that_never_answers_is_a_suite_error(monkeypatch):
    class _Response:
        status = 500

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(mockbank, "STARTUP_TIMEOUT_S", 0.01)
    monkeypatch.setattr(mockbank, "urlopen", lambda *a, **k: _Response())
    fake = types.SimpleNamespace(poll=lambda: None)
    with pytest.raises(SuiteError, match="did not become healthy"):
        mockbank._wait_until_healthy("http://127.0.0.1:1", fake)


def test_read_audit_returns_nothing_for_a_missing_state(tmp_path):
    assert mockbank.read_audit(tmp_path / "missing.sqlite") == []


def test_read_audit_keeps_a_detail_that_is_not_json(tmp_path):
    state = tmp_path / "mock.sqlite"
    with sqlite3.connect(state) as database:
        database.execute(
            "CREATE TABLE audit(seq INTEGER PRIMARY KEY, at TEXT, event TEXT, "
            "case_id TEXT, detail TEXT)"
        )
        database.execute(
            "INSERT INTO audit(at,event,case_id,detail) VALUES(?,?,?,?)",
            ("now", "tool_read", CASE, "not-json"),
        )
        database.commit()
    rows = mockbank.read_audit(state)
    assert rows[0]["detail"] == {"raw": "not-json"}


def test_stop_kills_a_process_that_will_not_wait():
    class _Process:
        stderr = None

        def __init__(self):
            self.waits = 0
            self.killed = False

        def terminate(self):
            pass

        def wait(self, timeout):
            self.waits += 1
            if self.waits == 1:
                raise subprocess.TimeoutExpired("mock", timeout)

        def kill(self):
            self.killed = True

    process = _Process()
    mockbank._stop(process)
    assert process.killed is True
    assert process.waits == 2


def test_stop_closes_stderr_when_it_has_one():
    class _Stderr:
        closed = False

        def close(self):
            self.closed = True

    class _Process:
        def __init__(self):
            self.stderr = _Stderr()

        def terminate(self):
            pass

        def wait(self, timeout):
            pass

        def kill(self):
            pass

    process = _Process()
    mockbank._stop(process)
    assert process.stderr.closed is True


def test_dataset_and_gold_that_disagree_fail_before_the_run():
    with pytest.raises(SuiteError, match="dataset and gold disagree"):
        runner._require_matching_ids(
            {"cases": [{"case_id": "A"}]},
            {"B": {}},
        )


def test_an_unreadable_case_list_becomes_a_suite_error(monkeypatch):
    from src import contract_records

    def _raise(*args, **kwargs):
        raise contract_records.CaseListError

    monkeypatch.setattr(contract_records, "load_contract_results", _raise)
    with pytest.raises(SuiteError, match="case list could not be read"):
        runner._build_contracts("http://127.0.0.1:1", Path("."))


def test_a_git_that_cannot_run_is_reported_as_unknown(monkeypatch):
    def _raise(*args, **kwargs):
        raise OSError("git missing")

    monkeypatch.setattr(runner.subprocess, "run", _raise)
    assert runner._commit() == "unknown"


def test_markdown_renders_gates_and_format_errors():
    run = make_run([make_case()], format_errors=["missing result: CASE-2"])
    summary = report.summarize(
        run,
        [report.Check("pii.restricted_values", CASE, True, "ok")],
        {"pii.restricted_values": 0.9},
    )
    text = report.render_markdown(summary)
    assert "## Gates" in text
    assert "## Format errors" in text
    assert "missing result: CASE-2" in text


def test_a_path_outside_the_repository_is_shown_absolute():
    assert report._display(Path("C:/Windows")).endswith("Windows")


def test_empty_names_render_as_none():
    assert report._names([]) == "none"
