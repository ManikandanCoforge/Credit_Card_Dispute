"""The qualification tool: what a model is asked, how each case is scored, what is registered.

No provider is called. A scripted model or a small recording answers, and every
registry is a temporary file, so models.toml is never changed by a test. Expected
outcomes come from ADR-003's scoring rule.
"""

import json
import tomllib

from src.model_clients import request_key
from src.model_cue import CUE_SCHEMA, CUE_SYSTEM, SCHEMA_HASH, evidence
from src.model_registry import find_qualified, load_registry
from tools import qualify_model
from tools.qualify_model import main, qualify, suite_lines, toml_entry

TWO_TIMES = "The shop took my money two times for one order."
QUOTED_LESS = "I was quoted 60 crowns but the shop took 90 crowns."
SUITE = [
    {
        "case_id": "Q-01",
        "suite": "synth",
        "expected_class": "duplicate_charge",
        "gap": True,
        "lines": [["Q-01-INTAKE:5", TWO_TIMES]],
    },
    {
        "case_id": "Q-02",
        "suite": "stress",
        "expected_class": "unsupported",
        "gap": False,
        "lines": [
            ["Q-02-INTAKE:5", QUOTED_LESS],
            ["Q-02-FOLLOWUP:7", "My card 4111 1111 1111 1111 was used."],
        ],
    },
]


class _Model:
    """A scripted live model: each question gets the next answer, and every question is kept."""

    provider = "azure_openai"
    model = "gpt-6-luna"

    def __init__(self, *answers):
        self._answers = list(answers)
        self.asked = []

    def ask(self, system, user, schema):
        self.asked.append(user)
        answer = self._answers.pop(0)
        return answer, {
            "purpose": "",
            "provider": self.provider,
            "model": self.model,
            "answered": answer is not None,
            "error": None if answer is not None else "timeout",
            "latency_ms": 12.5,
            "input_tokens": 230,
            "output_tokens": 9,
        }


def test_a_case_is_shown_as_its_recorded_lines_with_restricted_values_redacted():
    assert suite_lines(SUITE[1]) == [
        {"source_id": "Q-02-INTAKE", "text": QUOTED_LESS, "shown": QUOTED_LESS},
        {
            "source_id": "Q-02-FOLLOWUP",
            "text": "My card 4111 1111 1111 1111 was used.",
            "shown": "My card [redacted] was used.",
        },
    ]


def test_every_case_is_asked_once_and_scored_against_its_expected_class():
    model = _Model(
        {"type": "duplicate_charge", "line_id": "L1"}, {"type": "other_dispute", "line_id": "L1"}
    )

    rows = qualify(model, SUITE)

    assert rows == [
        {
            "case_id": "Q-01",
            "expected": "duplicate_charge",
            "gap": True,
            "proposal": "duplicate_charge",
            "outcome": "correct",
            "answered": True,
            "latency_ms": 12.5,
        },
        {
            "case_id": "Q-02",
            "expected": "unsupported",
            "gap": False,
            "proposal": "other_dispute",
            "outcome": "correct",
            "answered": True,
            "latency_ms": 12.5,
        },
    ]
    assert model.asked == [evidence(suite_lines(case)) for case in SUITE]


def test_an_unanswered_case_is_cautious_and_counts_as_not_answered():
    [row] = qualify(_Model(None), SUITE[:1])

    assert (row["proposal"], row["outcome"], row["answered"]) == (None, "cautious", False)
    assert row["latency_ms"] == 12.5


def test_a_case_without_lines_is_not_asked():
    model = _Model()

    [row] = qualify(model, [{**SUITE[0], "lines": []}])

    assert (row["proposal"], row["answered"], row["latency_ms"]) == (None, False, None)
    assert model.asked == []


def test_a_registry_entry_reads_back_as_the_record_without_its_empty_values():
    record = {
        "provider": "azure_openai",
        "model_id": "gpt-6-luna",
        "schema_hash": SCHEMA_HASH,
        "cases": 2,
        "median_latency_s": None,
        "approved_by": 'Dispute "ops" lead',
        "passed": True,
    }

    text = toml_entry(record)

    assert text.startswith("[[model]]\n")
    assert "passed = true\n" in text
    assert tomllib.loads(text)["model"] == [
        {key: value for key, value in record.items() if value is not None}
    ]


def test_main_without_a_model_says_what_to_set(tmp_path, capsys):
    assert main([str(_suite_file(tmp_path)), "--report", str(tmp_path / "report.json")]) == 1
    assert capsys.readouterr().err == "set MODEL_PROVIDER and the model's settings first\n"


def test_main_refuses_a_model_that_cannot_be_used(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "replay")

    assert main([str(_suite_file(tmp_path)), "--report", str(tmp_path / "report.json")]) == 1
    assert capsys.readouterr().err == "the model cannot be used: MODEL_REPLAY is not set\n"


def test_a_passed_live_run_is_reported_and_registered(tmp_path, capsys, monkeypatch):
    model = _Model(
        {"type": "duplicate_charge", "line_id": "L1"}, {"type": "other_dispute", "line_id": "L1"}
    )
    monkeypatch.setattr(qualify_model, "model_from_env", lambda env, **settings: model)
    report = tmp_path / "reports" / "luna.json"
    registry = tmp_path / "models.toml"

    status = main(
        [
            str(_suite_file(tmp_path)),
            "--report",
            str(report),
            "--register",
            "--registry",
            str(registry),
            "--approved-by",
            "Dispute operations lead",
            "--data-location",
            "East US",
        ]
    )

    assert status == 0
    written = json.loads(report.read_text(encoding="utf-8"))
    assert [row["outcome"] for row in written["cases"]] == ["correct", "correct"]
    entry = find_qualified(load_registry(registry), "azure_openai", "gpt-6-luna")
    assert entry is not None
    assert entry == {key: value for key, value in written["entry"].items() if value is not None}
    assert (entry["approved_by"], entry["data_location"]) == ("Dispute operations lead", "East US")
    assert capsys.readouterr().out == (
        "azure_openai/gpt-6-luna: 2 correct, 0 cautious, 0 unsafe of 2; passed\n"
        f"registered in {registry}\n"
    )


def test_a_failed_run_is_reported_but_never_registered(tmp_path, capsys, monkeypatch):
    model = _Model({"type": "unauthorized", "line_id": "L1"}, None)
    monkeypatch.setattr(qualify_model, "model_from_env", lambda env, **settings: model)
    suite, report, registry = _suite_file(tmp_path), tmp_path / "report.json", tmp_path / "m.toml"

    status = main([str(suite), "--report", str(report), "--register", "--registry", str(registry)])

    assert status == 1
    assert json.loads(report.read_text(encoding="utf-8"))["entry"]["unsafe"] == 1
    assert not registry.exists()
    assert capsys.readouterr().out == (
        "azure_openai/gpt-6-luna: 0 correct, 1 cautious, 1 unsafe of 2; failed\n"
    )


def test_a_recording_can_be_scored_but_a_replayed_run_is_never_registered(
    tmp_path, capsys, monkeypatch
):
    recording = tmp_path / "suite-answers.jsonl"
    answers = [{"type": "duplicate_charge", "line_id": "L1"}, {"type": "none", "line_id": "L1"}]
    recording.write_text(
        "".join(
            json.dumps(
                {
                    "key": request_key(CUE_SYSTEM, evidence(suite_lines(case)), CUE_SCHEMA),
                    "answer": answer,
                    "call": {
                        "purpose": "dispute_type",
                        "provider": "azure_openai",
                        "model": "gpt-6-luna",
                        "answered": True,
                        "error": None,
                        "latency_ms": 700.0,
                        "input_tokens": 200,
                        "output_tokens": 20,
                    },
                }
            )
            + "\n"
            for case, answer in zip(SUITE, answers)
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MODEL_PROVIDER", "replay")
    monkeypatch.setenv("MODEL_REPLAY", str(recording))
    suite, report, registry = _suite_file(tmp_path), tmp_path / "report.json", tmp_path / "m.toml"

    scored = main([str(suite), "--report", str(report)])
    refused = main([str(suite), "--report", str(report), "--register", "--registry", str(registry)])

    printed = capsys.readouterr()
    assert scored == 0
    assert printed.out == "replay/suite-answers: 1 correct, 1 cautious, 0 unsafe of 2; passed\n"
    assert refused == 1
    assert printed.err == "only a live model's run is registered, never a replayed one\n"
    assert not registry.exists()


def _suite_file(tmp_path):
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(SUITE), encoding="utf-8")
    return path
