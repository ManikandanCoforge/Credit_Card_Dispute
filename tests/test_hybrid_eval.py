"""The hybrid evaluation's scoring and report. No mock or model runs here.

summarize_pass is checked on results and an evaluation shaped like the bank
evaluator's output (tools/evaluate.py), render_table on a fixed report, and main on
its refusals. The suite runs themselves are the tool's job, not the unit tests'.
"""

from tools import hybrid_eval
from tools.hybrid_eval import evaluate_suite, main, render_table, summarize_pass

PASSING_CHECKS = {"classification": True, "routing": True, "deadline": True}


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
