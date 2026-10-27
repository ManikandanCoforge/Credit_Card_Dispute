"""The scored run: its pure helpers, and whole runs against the supplied mock.

The helper tests cover failed-check extraction, exception mapping, meter row
shape and report assembly, including a not-built case that must be reported
with its reason and submitted=false. The run tests start the supplied mock in
process on a free port with a temporary state, so they never touch a
developer's mock or the committed reports. They cover a full dev run, a failing
case, a run where every case passes, a zero-case run, an unreadable case list,
the command-line defaults and the script entry point. The full dev run reads
its p50 and p95 back out of the meter file the run wrote.
"""

import json
import runpy
import shutil
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest

from src.load_records import CaseListError
from src.meters import latency_percentiles
from tools.runtime import create_server
from tools.scored_run import (
    DETERMINISTIC_PATH,
    EXCEPTION_STATUS,
    assemble_report,
    build_case_reports,
    exception_list,
    failed_checks,
    main,
    measure_cases,
    meter_rows,
    proposed_exception,
    render_markdown,
    run_scored,
    run_succeeded,
    unplanned_failures,
)

_PASSING = {1, 2, 3, 4, 8, 11, 12}
_FAILING = {5, 6, 7, 9, 10}
ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "data" / "dev"
GOLD = ROOT / "feedback" / "dev_gold.json"


def test_failed_checks_are_the_sorted_false_names():
    checks = {"routing": True, "facts": False, "citations_valid": False}
    assert failed_checks(checks) == ["citations_valid", "facts"]


def test_failed_checks_is_empty_when_everything_passed():
    assert failed_checks({"routing": True, "facts": True}) == []


def test_a_not_submitted_case_fails_only_the_submitted_check():
    assert failed_checks({"submitted": False}) == ["submitted"]


@pytest.mark.parametrize(
    ("case_id", "ticket"),
    [
        ("CARD-D05", "COF-39"),
        ("CARD-D06", "COF-39"),
        ("CARD-D07", "COF-40"),
        ("CARD-D09", "COF-43"),
        ("CARD-D10", "COF-40"),
    ],
)
def test_each_failing_dev_case_maps_to_a_proposed_ticket(case_id, ticket):
    mapping = proposed_exception(case_id)
    assert mapping is not None
    assert mapping[0] == ticket
    assert mapping[1]


def test_a_passing_case_has_no_proposed_ticket():
    assert proposed_exception("CARD-D01") is None


def test_another_failure_of_a_mapped_case_is_not_excused():
    assert proposed_exception("CARD-D05", ["submitted"]) is not None
    assert proposed_exception("CARD-D05", ["transaction_facts"]) is None


def test_exception_entries_are_explicitly_pending_pod_agreement():
    reports = [
        _case(
            "CARD-D05",
            submitted=False,
            passed=False,
            failed=["submitted"],
            error="the case names evidence this step cannot read: CARD-D05-FOLLOWUP",
        )
    ]

    entries = exception_list(reports)

    assert len(entries) == 1
    entry = entries[0]
    assert entry["case_id"] == "CARD-D05"
    assert entry["ticket"] == "COF-39"
    assert entry["status"] == "proposed_pending_pod_agreement"
    assert entry["failed_checks"] == ["submitted"]
    assert entry["error"].startswith("the case names evidence")
    assert entry["note"]


def test_exception_list_skips_passing_cases():
    assert exception_list([_case("CARD-D01", passed=True)]) == []


def test_an_unmapped_failure_is_not_excused():
    reports = [_case("CARD-D99", passed=False, failed=["routing"], error=None)]

    assert exception_list(reports) == []
    assert unplanned_failures(reports) == [
        {"case_id": "CARD-D99", "failed_checks": ["routing"], "error": None}
    ]


def test_meter_rows_are_one_measured_deterministic_row_per_case():
    reports = [
        _case("CARD-D01", duration=1.234),
        _case("CARD-D02", duration=2.5),
    ]

    rows = meter_rows(reports)

    assert [row["case_id"] for row in rows] == ["CARD-D01", "CARD-D02"]
    assert rows[0] == {
        "case_id": "CARD-D01",
        "duration_ms": 1.234,
        "model_calls": 0,
        "model_tokens_in": 0,
        "model_tokens_out": 0,
        "cost_usd": 0.0,
        "path": DETERMINISTIC_PATH,
    }
    assert all(row["path"] == "deterministic_template" for row in rows)
    assert all(row["cost_usd"] == 0.0 for row in rows)


def test_a_not_built_case_is_reported_with_its_reason_and_submitted_false():
    measured = [
        {
            "case_id": "CARD-D05",
            "duration_ms": 1.5,
            "contract": None,
            "error": (
                "the case names evidence this step cannot read: CARD-D05-FOLLOWUP"
            ),
        }
    ]
    evaluation = _evaluation(
        [{"case_id": "CARD-D05", "passed": False, "checks": {"submitted": False}}]
    )

    assert build_case_reports(measured, evaluation) == [
        {
            "case_id": "CARD-D05",
            "submitted": False,
            "passed": False,
            "duration_ms": 1.5,
            "failed_checks": ["submitted"],
            "error": (
                "the case names evidence this step cannot read: CARD-D05-FOLLOWUP"
            ),
            "meter_error": None,
        }
    ]


def test_a_built_case_carries_every_failed_check_from_the_evaluator():
    measured = [
        {
            "case_id": "CARD-D06",
            "duration_ms": 2.0,
            "contract": {"case_id": "CARD-D06"},
            "error": None,
        }
    ]
    evaluation = _evaluation(
        [
            {
                "case_id": "CARD-D06",
                "passed": False,
                "checks": {
                    "classification": False,
                    "routing": False,
                    "citations_valid": True,
                },
            }
        ]
    )

    report = build_case_reports(measured, evaluation)[0]

    assert report["submitted"] is True
    assert report["failed_checks"] == ["classification", "routing"]


def test_a_case_the_evaluator_never_mentions_is_not_a_pass():
    measured = [
        {
            "case_id": "CARD-DXX",
            "duration_ms": 0.5,
            "contract": {"case_id": "CARD-DXX"},
            "error": None,
        }
    ]

    report = build_case_reports(measured, _evaluation([]))[0]

    assert report["passed"] is False
    assert report["failed_checks"] == ["missing_from_evaluation"]


def test_assemble_report_carries_counts_and_the_supplied_percentiles():
    reports = [
        _case("CARD-D01", passed=True, duration=1.0),
        _case(
            "CARD-D05",
            submitted=False,
            passed=False,
            duration=3.0,
            failed=["submitted"],
            error="follow-up unread",
        ),
    ]

    report = assemble_report(
        reports,
        _evaluation([]),
        generated_at="2026-10-25T00:00:00Z",
        git_commit="abc123",
        git_dirty=True,
        base_url="http://127.0.0.1:8899",
        dataset_name="card-disputes-dev",
        latencies={"p50": 2, "p95": 5},
    )

    assert report["pass_count"] == 1
    assert report["total_cases"] == 2
    assert report["format_errors"] == []
    assert report["p50_latency_ms"] == 2
    assert report["p95_latency_ms"] == 5
    assert report["cost_per_case_usd"] == 0.0
    assert report["total_cost_usd"] == 0.0
    assert report["cases"] == reports
    assert report["exceptions"][0]["case_id"] == "CARD-D05"
    assert report["exception_status"] == EXCEPTION_STATUS
    assert report["generated_at"] == "2026-10-25T00:00:00Z"
    assert "0 model calls" in report["cost_note"]


@pytest.mark.parametrize(
    ("pass_count", "total_cases", "format_errors", "expected"),
    [
        (12, 12, [], True),
        (12, 12, ["Unexpected case: X"], False),
        (11, 12, [], False),
        (0, 12, [], False),
        (7, 7, [], True),
        (0, 0, [], False),
    ],
)
def test_exit_is_success_only_when_every_case_passes(
    pass_count, total_cases, format_errors, expected
):
    report = {
        "pass_count": pass_count,
        "total_cases": total_cases,
        "format_errors": format_errors,
    }
    assert run_succeeded(report) is expected


def test_markdown_states_the_pass_count_and_format_errors():
    markdown = render_markdown(_twelve_case_report(), meter_rows(_twelve_cases()))
    assert "Pass: 7 / 12" in markdown
    assert "Format errors: 0" in markdown


def test_markdown_names_every_failing_case_and_its_exact_check():
    markdown = render_markdown(_twelve_case_report(), meter_rows(_twelve_cases()))
    for number in sorted(_FAILING):
        assert f"CARD-D{number:02d}" in markdown
    assert "submitted" in markdown


def test_markdown_marks_the_exceptions_as_proposed_not_agreed():
    markdown = render_markdown(_twelve_case_report(), meter_rows(_twelve_cases()))
    lowered = markdown.lower()
    assert "proposed, pending pod agreement" in lowered
    assert "not agreed scope" in lowered


def test_markdown_reports_both_percentiles_from_the_meter_file():
    markdown = render_markdown(_twelve_case_report(), meter_rows(_twelve_cases()))
    assert "- p50 draft latency: 6.000 ms" in markdown
    assert "- p95 draft latency: 12.000 ms" in markdown
    assert "reports/meters.jsonl" in markdown
    assert "Cost per case: 0.00 USD" in markdown
    assert "reports/scored-run-meters.json" in markdown


def test_markdown_contains_the_exact_reproduction_commands():
    markdown = render_markdown(_twelve_case_report(), meter_rows(_twelve_cases()))
    assert (
        "uv run --locked python tools/runtime.py reset --confirm "
        "--state .state/scored-run.sqlite\n"
    ) in markdown
    assert (
        "uv run --locked python tools/runtime.py serve --data data/dev --port 8765 "
        "--state .state/scored-run.sqlite\n"
    ) in markdown
    assert (
        "uv run --locked python tools/scored_run.py --base-url http://127.0.0.1:8765 "
        "--data data/dev --gold feedback/dev_gold.json "
        "--case-meters reports/meters.jsonl\n"
    ) in markdown


def test_the_reproduction_commands_run_the_same_on_any_operating_system():
    markdown = render_markdown(_twelve_case_report(), meter_rows(_twelve_cases()))
    commands = markdown.split("## Reproduce", 1)[1]
    for unportable in ("Scripts", ".exe", "../", "rm -f", " &\n", "\\\n"):
        assert unportable not in commands


def test_the_markdown_names_the_meter_file_the_run_actually_wrote(tmp_path, monkeypatch):
    paths = _outputs(tmp_path)
    elsewhere = tmp_path / "case-meters" / "elsewhere.jsonl"
    paths["case_meter_path"] = elsewhere
    monkeypatch.setattr("tools.scored_run.contract_case_plans", lambda base, data: [])

    status = run_scored(
        base_url="http://127.0.0.1:8765", data_dir=DEV, gold_path=GOLD, **_run(paths)
    )

    markdown = paths["markdown_path"].read_text(encoding="utf-8")
    assert status == 1
    assert f"--case-meters {elsewhere}" in markdown
    assert str(elsewhere) in markdown
    assert "reports/meters.jsonl" not in markdown


def test_an_unreadable_case_list_writes_nothing_and_keeps_the_last_report(
    tmp_path, monkeypatch, capsys
):
    def unreachable(base_url, data_dir):
        raise CaseListError

    monkeypatch.setattr("tools.scored_run.contract_case_plans", unreachable)
    paths = {
        "submission_path": tmp_path / "submissions" / "scored-run.json",
        "report_path": tmp_path / "reports" / "scored-run.json",
        "meters_path": tmp_path / "reports" / "scored-run-meters.json",
        "markdown_path": tmp_path / "reports" / "scored-run.md",
        "case_meter_path": tmp_path / "reports" / "meters.jsonl",
    }
    paths["report_path"].parent.mkdir()
    for name in ("report_path", "meters_path", "markdown_path"):
        paths[name].write_text("the last published run\n", encoding="utf-8")

    status = run_scored(
        base_url="http://127.0.0.1:8765",
        data_dir=ROOT / "data" / "dev",
        gold_path=ROOT / "feedback" / "dev_gold.json",
        generated_at="2026-10-27T00:00:00Z",
        git_commit="abc123",
        git_dirty=False,
        **paths,
    )

    assert status == 1
    assert not paths["submission_path"].exists()
    for name in ("report_path", "meters_path", "markdown_path"):
        assert paths[name].read_text(encoding="utf-8") == "the last published run\n"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "could not be read from http://127.0.0.1:8765" in captured.err
    assert "Nothing was written" in captured.err


def test_a_restricted_value_in_the_meter_file_fails_the_run_and_names_it(
    tmp_path, monkeypatch, capsys
):
    paths = _outputs(tmp_path)
    paths["case_meter_path"].parent.mkdir(parents=True)
    paths["case_meter_path"].write_text(
        json.dumps(
            {"case_id": "CARD-D01", "route": "4111-1111-1111-1111", "latency_ms": 5}
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("tools.scored_run.contract_case_plans", lambda base, data: [])
    monkeypatch.setattr(
        "tools.scored_run.measure_cases",
        lambda plans, base, data, *, build=None, meter_path=None: [],
    )

    status = run_scored(
        base_url="http://127.0.0.1:8765", data_dir=DEV, gold_path=GOLD, **_run(paths)
    )

    assert status == 1
    assert not paths["report_path"].exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert str(paths["case_meter_path"]) in captured.err
    assert "CARD-D01" in captured.err


def test_a_full_dev_run_against_the_mock_writes_four_artifacts_that_agree(
    tmp_path, capsys
):
    paths = _outputs(tmp_path)

    with _mock(DEV, tmp_path) as base_url:
        status = run_scored(base_url=base_url, data_dir=DEV, gold_path=GOLD, **_run(paths))

    report, meters, submission = _written(paths)
    latencies = latency_percentiles(paths["case_meter_path"])
    assert len(paths["case_meter_path"].read_text(encoding="utf-8").splitlines()) == 12
    assert report["p50_latency_ms"] == latencies["p50"]
    assert report["p95_latency_ms"] == latencies["p95"]
    assert status == (0 if run_succeeded(report) else 1)
    assert report["total_cases"] == len(meters) == 12
    assert report["format_errors"] == []
    assert report["base_url"] == base_url
    assert report["pass_count"] == sum(1 for case in report["cases"] if case["passed"])
    assert [contract["case_id"] for contract in submission] == [
        case["case_id"] for case in report["cases"] if case["submitted"]
    ]
    assert paths["markdown_path"].read_text(encoding="utf-8") == render_markdown(
        report, meters, meter_path=str(paths["case_meter_path"])
    )
    printed = capsys.readouterr().out.splitlines()
    assert printed[0].startswith(
        f"{report['pass_count']} / 12 cases passed; 0 format errors; p50 "
    )
    assert f"p95 {report['p95_latency_ms']:.3f} ms" in printed[0]
    failing = [case["case_id"] for case in report["cases"] if not case["passed"]]
    assert [line.split(":")[0].strip() for line in printed[1:]] == failing


def test_a_failing_case_is_printed_with_its_checks_and_the_run_exits_1(
    tmp_path, capsys
):
    data_dir, gold_path = _case_set(
        tmp_path, ["CARD-D01", "CARD-D02"], {"CARD-D02": {"routing": "manual_review"}}
    )
    paths = _outputs(tmp_path)

    with _mock(data_dir, tmp_path) as base_url:
        status = run_scored(
            base_url=base_url, data_dir=data_dir, gold_path=gold_path, **_run(paths)
        )

    report, _meters, _submission = _written(paths)
    assert status == 1
    assert (report["pass_count"], report["total_cases"]) == (1, 2)
    [failing] = [case for case in report["cases"] if not case["passed"]]
    assert failing["case_id"] == "CARD-D02"
    assert "routing" in failing["failed_checks"]
    assert report["unplanned_failures"] == [
        {"case_id": "CARD-D02", "failed_checks": failing["failed_checks"], "error": None}
    ]
    markdown = paths["markdown_path"].read_text(encoding="utf-8")
    assert "### Unplanned failures (not exceptions)" in markdown
    assert "None. No failing case has a proposed ticket." in markdown
    assert capsys.readouterr().out.splitlines()[1:] == [
        f"  CARD-D02: {', '.join(failing['failed_checks'])}"
    ]


def test_a_run_where_every_case_passes_exits_0(tmp_path, capsys):
    data_dir, gold_path = _case_set(tmp_path, ["CARD-D01"])
    paths = _outputs(tmp_path)

    with _mock(data_dir, tmp_path) as base_url:
        status = run_scored(
            base_url=base_url, data_dir=data_dir, gold_path=gold_path, **_run(paths)
        )

    report, _meters, _submission = _written(paths)
    assert status == 0
    assert (report["pass_count"], report["total_cases"]) == (1, 1)
    assert "None. Every case passed." in paths["markdown_path"].read_text(encoding="utf-8")
    assert capsys.readouterr().out.splitlines()[1:] == []


def test_a_zero_case_run_reports_no_latency_and_exits_1(tmp_path, capsys):
    data_dir, gold_path = _case_set(tmp_path, [])
    paths = _outputs(tmp_path)

    with _mock(data_dir, tmp_path) as base_url:
        status = run_scored(
            base_url=base_url, data_dir=data_dir, gold_path=gold_path, **_run(paths)
        )

    report, _meters, submission = _written(paths)
    assert status == 1
    assert report["total_cases"] == 0
    assert report["p50_latency_ms"] is None
    assert report["p95_latency_ms"] is None
    assert submission == []
    assert paths["case_meter_path"].read_text(encoding="utf-8") == ""
    markdown = paths["markdown_path"].read_text(encoding="utf-8")
    assert "- p50 draft latency: -" in markdown
    assert "- p95 draft latency: -" in markdown
    assert capsys.readouterr().out.splitlines()[0] == (
        "0 / 0 cases passed; 0 format errors; p50 -; p95 -; cost per case 0.00 USD"
    )


def test_the_script_runs_from_another_directory_without_the_repository_on_sys_path(
    tmp_path, monkeypatch
):
    data_dir, gold_path = _case_set(tmp_path, ["CARD-D01"])
    paths = _outputs(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", [entry for entry in sys.path if entry != str(ROOT)])

    with _mock(data_dir, tmp_path) as base_url:
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "scored_run.py",
                *("--base-url", base_url, "--data", str(data_dir), "--gold", str(gold_path)),
                *("--submission", str(paths["submission_path"])),
                *("--report", str(paths["report_path"])),
                *("--meters", str(paths["meters_path"])),
                *("--markdown", str(paths["markdown_path"])),
                *("--case-meters", str(paths["case_meter_path"])),
            ],
        )
        with pytest.raises(SystemExit) as exited:
            runpy.run_path(str(ROOT / "tools" / "scored_run.py"), run_name="__main__")

    assert exited.value.code == 0
    assert sys.path[0] == str(ROOT)
    assert paths["report_path"].exists()


def test_the_run_reads_the_mock_on_the_readme_port_by_default(monkeypatch):
    seen = {}

    def record(**arguments):
        seen.update(arguments)
        return 0

    monkeypatch.setattr("tools.scored_run.run_scored", record)

    assert main([]) == 0
    assert seen["base_url"] == "http://127.0.0.1:8765"
    assert seen["data_dir"] == ROOT / "data" / "dev"
    assert seen["gold_path"] == ROOT / "feedback" / "dev_gold.json"


@contextmanager
def _mock(data_dir, tmp_path):
    server = create_server(data_dir, tmp_path / "mock.sqlite", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def _case_set(tmp_path, case_ids, gold_changes=None):
    """A copy of the dev set listing only case_ids, and its gold with any changes."""
    data_dir = tmp_path / "data"
    shutil.copytree(DEV, data_dir)
    dataset = json.loads((data_dir / "dataset.json").read_text(encoding="utf-8"))
    dataset["cases"] = [case for case in dataset["cases"] if case["case_id"] in case_ids]
    (data_dir / "dataset.json").write_text(json.dumps(dataset), encoding="utf-8")
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    changes = gold_changes or {}
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(
        json.dumps({case_id: {**gold[case_id], **changes.get(case_id, {})} for case_id in case_ids}),
        encoding="utf-8",
    )
    return data_dir, gold_path


def _outputs(tmp_path):
    """Artifact paths in directories that do not exist yet."""
    return {
        "submission_path": tmp_path / "out" / "submissions" / "scored-run.json",
        "report_path": tmp_path / "out" / "reports" / "scored-run.json",
        "meters_path": tmp_path / "out" / "reports" / "scored-run-meters.json",
        "markdown_path": tmp_path / "out" / "reports" / "scored-run.md",
        "case_meter_path": tmp_path / "out" / "reports" / "meters.jsonl",
    }


def _run(paths):
    return {
        **paths,
        "generated_at": "2026-10-27T00:00:00Z",
        "git_commit": "abc123",
        "git_dirty": False,
    }


def _written(paths):
    return tuple(
        json.loads(paths[name].read_text(encoding="utf-8"))
        for name in ("report_path", "meters_path", "submission_path")
    )


def _case(
    case_id,
    *,
    submitted=True,
    passed=True,
    duration=1.0,
    failed=None,
    error=None,
):
    return {
        "case_id": case_id,
        "submitted": submitted,
        "passed": passed,
        "duration_ms": duration,
        "failed_checks": [] if failed is None else list(failed),
        "error": error,
    }


def _evaluation(cases):
    return {
        "passed": False,
        "format_errors": [],
        "cases": cases,
        "passed_cases": sum(1 for case in cases if case["passed"]),
        "total_cases": len(cases),
    }


def _twelve_cases():
    cases = []
    for number in range(1, 13):
        case_id = f"CARD-D{number:02d}"
        if number in _PASSING:
            cases.append(_case(case_id, duration=float(number)))
        else:
            cases.append(
                _case(
                    case_id,
                    submitted=False,
                    passed=False,
                    duration=float(number),
                    failed=["submitted"],
                    error=f"{case_id} was not built",
                )
            )
    return cases


def _twelve_latencies():
    return {"p50": 6, "p95": 12}


def _twelve_case_report():
    return assemble_report(
        _twelve_cases(),
        _evaluation([]),
        generated_at="2026-10-25T00:00:00Z",
        git_commit="abc123",
        git_dirty=True,
        base_url="http://127.0.0.1:8899",
        dataset_name="card-disputes-dev",
        latencies=_twelve_latencies(),
    )


def test_report_cost_is_read_from_the_supplied_meter_rows():
    reports = [
        _case("CARD-D01", passed=True, duration=1.0),
        _case("CARD-D02", passed=True, duration=2.0),
    ]
    meters = [
        {
            "case_id": "CARD-D01",
            "duration_ms": 1.0,
            "model_calls": 1,
            "model_tokens_in": 10,
            "model_tokens_out": 5,
            "cost_usd": 0.30,
            "path": "model_prose",
        },
        {
            "case_id": "CARD-D02",
            "duration_ms": 2.0,
            "model_calls": 1,
            "model_tokens_in": 10,
            "model_tokens_out": 5,
            "cost_usd": 0.10,
            "path": "model_prose",
        },
    ]

    report = assemble_report(
        reports,
        _evaluation([]),
        generated_at="2026-10-25T00:00:00Z",
        git_commit="abc123",
        git_dirty=False,
        base_url="http://127.0.0.1:8899",
        dataset_name="card-disputes-dev",
        latencies={"p50": 1, "p95": 2},
        meters=meters,
    )

    assert report["total_cost_usd"] == 0.4
    assert report["cost_per_case_usd"] == 0.2


def test_the_git_commit_note_tracks_the_dirty_flag():
    common = {
        "evaluation": _evaluation([]),
        "generated_at": "2026-10-25T00:00:00Z",
        "git_commit": "abc123",
        "base_url": "http://127.0.0.1:8899",
        "dataset_name": "card-disputes-dev",
        "latencies": {"p50": 1, "p95": 2},
    }

    clean = assemble_report([_case("CARD-D01")], git_dirty=False, **common)
    dirty = assemble_report([_case("CARD-D01")], git_dirty=True, **common)

    assert "working tree was clean" in clean["git_commit_note"]
    assert "uncommitted changes" in dirty["git_commit_note"]


def test_measure_cases_times_the_injected_builder(tmp_path):
    plans = [{"record": {"case_id": "CARD-D01"}, "documents": []}]
    seen = []

    def build(plan):
        seen.append(plan["record"]["case_id"])
        return {"case_id": "CARD-D01", "contract": None, "error": "stop"}

    measured = measure_cases(plans, "http://127.0.0.1:8899", tmp_path, build=build)

    assert seen == ["CARD-D01"]
    assert measured == [
        {
            "case_id": "CARD-D01",
            "duration_ms": measured[0]["duration_ms"],
            "contract": None,
            "error": "stop",
            "meter_error": None,
        }
    ]
    assert measured[0]["duration_ms"] >= 0.0


def test_a_refused_meter_line_is_named_in_the_report(tmp_path):
    plans = [{"record": {"case_id": "CARD-D01"}, "documents": []}]

    def build(plan):
        return {
            "case_id": "CARD-D01",
            "contract": None,
            "error": None,
            "meter_error": "MeterLeak",
        }

    measured = measure_cases(plans, "http://127.0.0.1:8899", tmp_path, build=build)
    reports = build_case_reports(
        measured,
        _evaluation(
            [{"case_id": "CARD-D01", "passed": False, "checks": {"submitted": False}}]
        ),
    )
    report = assemble_report(
        reports,
        _evaluation([]),
        generated_at="2026-10-27T00:00:00Z",
        git_commit="abc123",
        git_dirty=False,
        base_url="http://127.0.0.1:8899",
        dataset_name="card-disputes-dev",
        latencies={"p50": None, "p95": None},
        meters=meter_rows(reports),
    )

    assert report["cases"][0]["meter_error"] == "MeterLeak"
    markdown = render_markdown(report, meter_rows(reports))
    assert "CARD-D01" in markdown
    assert "MeterLeak" in markdown


def test_the_committed_report_matches_its_meters_and_markdown():
    report = json.loads((ROOT / "reports" / "scored-run.json").read_text())
    meters = json.loads((ROOT / "reports" / "scored-run-meters.json").read_text())
    markdown = (ROOT / "reports" / "scored-run.md").read_text()

    assert report["total_cases"] == len(meters) == 12
    assert report["pass_count"] == sum(1 for case in report["cases"] if case["passed"])
    committed_meters = ROOT / "reports" / "meters.jsonl"
    latencies = latency_percentiles(committed_meters)
    assert isinstance(latencies["p50"], int)
    assert isinstance(latencies["p95"], int)
    assert report["p50_latency_ms"] == latencies["p50"]
    assert report["p95_latency_ms"] == latencies["p95"]
    assert report["p50_latency_ms"] <= report["p95_latency_ms"]
    assert report["total_cost_usd"] == round(
        sum(row["cost_usd"] for row in meters), 6
    )
    assert report["exception_status"] == EXCEPTION_STATUS
    assert markdown == render_markdown(report, meters)
