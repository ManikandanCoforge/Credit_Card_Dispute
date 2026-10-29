"""The hybrid evaluation's scoring, its report, and one whole run.

summarize_pass is checked on results and an evaluation shaped like the bank
evaluator's output (tools/evaluate.py), render_table on a fixed report, and main on
its refusals. One test runs main on the dev suite with recorded answers, against the
unmodified mock on a free port, as the README's replay command does. No live model
is called anywhere.
"""

import json
import runpy
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import hybrid_eval
from tools.hybrid_eval import evaluate_suite, main, render_table, summarize_pass

PASSING_CHECKS = {"classification": True, "routing": True, "deadline": True}
ROOT = Path(__file__).resolve().parents[1]
RECORDING = ROOT / "evals" / "recordings" / "gpt-6-luna.jsonl"


def _result(case_id, routing=None, calls=(), error=None):
    contract = None if routing is None else {"case_id": case_id, "routing": routing}
    return {
        "case_id": case_id,
        "contract": contract,
        "error": error,
        "narrative_meter": None,
        "model_calls": list(calls),
    }


def _call(purpose, tokens=(None, None), error=None):
    return {
        "purpose": purpose,
        "provider": "azure_openai",
        "model": "gpt-6-luna",
        "answered": error is None,
        "error": error,
        "latency_ms": 800.0,
        "input_tokens": tokens[0],
        "output_tokens": tokens[1],
    }


def test_a_pass_counts_wrong_ready_drafts_manual_reviews_unbuilt_cases_and_model_use():
    results = [
        _result("A", "ready_for_review", [_call("multiple_problems", (100, 10))]),
        _result("B", "ready_for_review", [_call("multiple_problems", (120, 12))]),
        _result("C", "manual_review"),
        _result("D", calls=[_call("dispute_type", error="no_recording")], error="BankReadError"),
    ]
    evaluation = {
        "cases": [
            {"case_id": "A", "passed": True, "checks": PASSING_CHECKS},
            {
                "case_id": "B",
                "passed": False,
                "checks": {**PASSING_CHECKS, "routing": False, "deadline": False},
            },
            {"case_id": "C", "passed": True, "checks": PASSING_CHECKS},
            {"case_id": "D", "passed": False, "checks": {"submitted": False}},
        ],
        "format_errors": [],
    }

    assert summarize_pass(results, evaluation) == {
        "passed": 2,
        "total": 4,
        "failed": {"B": ["deadline", "routing"], "D": ["submitted"]},
        "not_built_reasons": {"D": "BankReadError"},
        "wrong_ready": ["B"],
        "manual_review": 1,
        "not_built": ["D"],
        "format_errors": [],
        "model_calls": 3,
        "model_answers": 2,
        "input_tokens": 220,
        "output_tokens": 22,
    }


def test_each_suite_runs_the_rules_alone_then_the_hybrid(monkeypatch):
    runs = []
    model = object()
    monkeypatch.setattr(
        hybrid_eval, "run_pass", lambda data_dir, port, used: runs.append((port, used)) or []
    )
    monkeypatch.setattr(
        hybrid_eval,
        "evaluate",
        lambda dataset, gold, submissions: {"cases": [], "format_errors": []},
    )

    report = evaluate_suite("dev", model, 8901)

    assert runs == [(8901, None), (8901, model)]
    assert report["suite"] == "dev"
    assert report["rules"]["total"] == report["hybrid"]["total"] == 0


def test_the_table_shows_rules_above_the_hybrid_for_each_suite():
    def row(passed, total, wrong_ready, manual, not_built, calls, tokens):
        return {
            "passed": passed,
            "total": total,
            "wrong_ready": wrong_ready,
            "manual_review": manual,
            "not_built": not_built,
            "model_calls": calls,
            "input_tokens": tokens[0],
            "output_tokens": tokens[1],
        }

    table = render_table(
        [
            {
                "suite": "stress",
                "rules": row(5, 16, ["STR-P15"], 2, ["STR-P01"], 0, (0, 0)),
                "hybrid": row(16, 16, [], 9, [], 16, (5585, 647)),
            }
        ]
    )

    header, rule, *rows = table.splitlines()
    assert header == (
        "Suite    Design     Passed  Wrong ready  Manual  Not built  Calls   Tokens in/out"
    )
    assert rule == "-" * len(header)
    assert rows == [
        "stress   rules      5 / 16             1       2          1      0       0/0      ",
        "stress   hybrid    16 / 16             0       9          0     16    5585/647    ",
    ]


def test_main_says_which_setting_to_use_when_no_model_is_named(capsys):
    assert main(["--suites", "dev"]) == 1
    assert capsys.readouterr().err == (
        "set MODEL_PROVIDER (for example replay with MODEL_REPLAY) first\n"
    )


def test_main_refuses_a_model_that_cannot_be_used(capsys, monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "azure_openai")

    assert main(["--suites", "dev"]) == 1
    assert capsys.readouterr().err == "the model cannot be used: MODEL_ID is not set\n"


def test_main_runs_the_dev_suite_against_the_mock_with_recorded_answers(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.setenv("MODEL_PROVIDER", "replay")
    monkeypatch.setenv("MODEL_REPLAY", str(RECORDING))
    report_path = tmp_path / "reports" / "hybrid-eval.json"

    status = main(["--suites", "dev", "--report", str(report_path), "--port", str(_free_port())])

    assert status == 0
    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert written["model"].startswith("replay/")
    assert written["git_commit"]
    assert written["generated_at"].endswith("Z")
    [suite] = written["suites"]
    dataset = json.loads((ROOT / "data" / "dev" / "dataset.json").read_text(encoding="utf-8"))
    assert suite["suite"] == "dev"
    assert suite["rules"]["total"] == suite["hybrid"]["total"] == len(dataset["cases"])
    assert suite["rules"]["model_calls"] == 0
    assert suite["hybrid"]["model_calls"] > 0
    assert suite["rules"]["format_errors"] == suite["hybrid"]["format_errors"] == []
    printed = capsys.readouterr().out
    assert printed == f"Model: {written['model']}\n{render_table(written['suites'])}\n"


def _row(passed=0, total=0, failed=None, not_built=None, format_errors=None):
    return {
        "passed": passed,
        "total": total,
        "failed": failed or {},
        "not_built_reasons": not_built or {},
        "wrong_ready": [],
        "manual_review": 0,
        "not_built": sorted((not_built or {})),
        "format_errors": format_errors or [],
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
    }


def test_the_markdown_report_names_the_model_commit_and_every_failure():
    report = {
        "model": "azure_openai/gpt-6-luna",
        "git_commit": "26d70c3",
        "generated_at": "2026-10-29T05:40:00Z",
        "suites": [
            {
                "suite": "synth",
                "rules": _row(
                    25,
                    31,
                    failed={"SYN-S26": ["classification", "deadline", "routing"]},
                ),
                "hybrid": _row(
                    30,
                    31,
                    failed={"SYN-S26": ["classification", "deadline", "routing"]},
                    not_built={"SYN-S27": "BankReadError"},
                    format_errors=["the submission for SYN-S28 has no case_id"],
                ),
            }
        ],
    }

    text = hybrid_eval.render_markdown(report)

    assert text.startswith("# Hybrid model run\n\n")
    assert "Model: `azure_openai/gpt-6-luna`" in text
    assert "Commit: `26d70c3`" in text
    assert "Generated: 2026-10-29T05:40:00Z" in text
    assert "| synth | rules | 25 / 31 | 0 | 0 | 0 | 0 | 0 / 0 |" in text
    assert "- synth / rules: SYN-S26 (classification, deadline, routing)" in text
    assert "- synth / hybrid: SYN-S27 not built (BankReadError)" in text
    assert "- synth / hybrid format: the submission for SYN-S28 has no case_id" in text


def test_the_markdown_report_says_none_when_everything_passed():
    report = {
        "model": "replay/gpt-6-luna",
        "git_commit": "abc1234",
        "generated_at": "2026-10-29T05:40:00Z",
        "suites": [{"suite": "dev", "rules": _row(12, 12), "hybrid": _row(12, 12)}],
    }

    assert "## Failures\n\nNone.\n" in hybrid_eval.render_markdown(report)


def test_git_commit_is_unknown_when_git_cannot_run(monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("no git on this host")

    monkeypatch.setattr(hybrid_eval.subprocess, "run", broken)

    assert hybrid_eval._git_commit() == "unknown"


def test_main_writes_the_markdown_report_beside_the_json(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(
        hybrid_eval,
        "model_from_env",
        lambda env: SimpleNamespace(provider="replay", model="test"),
    )
    row = _row(12, 12)
    monkeypatch.setattr(
        hybrid_eval,
        "evaluate_suite",
        lambda name, model, port: {"suite": name, "rules": row, "hybrid": row},
    )
    report_path = tmp_path / "reports" / "hybrid-eval.json"
    markdown_path = tmp_path / "reports" / "hybrid-eval.md"

    status = main(
        [
            "--suites",
            "dev",
            "--report",
            str(report_path),
            "--markdown",
            str(markdown_path),
        ]
    )

    assert status == 0
    assert report_path.exists()
    assert "Model: `replay/test`" in markdown_path.read_text(encoding="utf-8")
    assert capsys.readouterr().out.startswith("Model: replay/test\n")


def test_waiting_for_the_mock_gives_up_after_its_deadline(monkeypatch):
    clock = iter([0.0, 1.0, 16.0])
    slept = []

    def refused(url, timeout):
        raise ConnectionRefusedError(url)

    monkeypatch.setattr(hybrid_eval.urllib.request, "urlopen", refused)
    monkeypatch.setattr(hybrid_eval.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(hybrid_eval.time, "sleep", slept.append)

    with pytest.raises(ConnectionRefusedError):
        hybrid_eval._wait_for("http://127.0.0.1:9")

    assert slept == [0.1]


def test_the_script_runs_without_the_repository_on_sys_path(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", [entry for entry in sys.path if entry != str(ROOT)])
    monkeypatch.setattr(sys, "argv", ["hybrid_eval.py", "--suites", "dev"])

    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(ROOT / "tools" / "hybrid_eval.py"), run_name="__main__")

    assert exited.value.code == 1
    assert sys.path[0] == str(ROOT)
    assert "set MODEL_PROVIDER" in capsys.readouterr().err


def _free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]
