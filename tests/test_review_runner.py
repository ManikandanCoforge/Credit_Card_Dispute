"""Each finished draft gets a human review, and only an approved, unchanged draft is recorded.

The bank is the mock service on the dev dataset, and the reviewer is the operator
command run from the test, as a person would run it in another terminal.
"""

import json
import runpy
import sqlite3
import subprocess
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from src.contract_records import ToolRetry
from src.idempotency import CreateRejected
from src.review_gate import ReviewRefused
from src.review_runner import (
    check_reviews,
    main,
    read_journal,
    submit_drafts,
    write_journal,
)
from tools.runtime import create_server

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "data" / "dev"

# The mechanisms by which the application could bypass the human gate: run the
# operator command (a child process, the runtime module, its reviewer flag), approve
# a review itself (write the review table or call an approval endpoint), or claim an
# approval event it did not receive.
#
# src/run_loop.py is the one-command loop: it starts the supplied mock and does
# nothing else. Its own tests assert the argv verb is "serve" and that the state file
# is its own, so it may use the process-launch markers and no others. The exemption
# is data, so a second file needs a deliberate edit here.
_LAUNCH_MARKERS = frozenset(
    {"subprocess", "runtime.py", "tools.runtime", "tools/runtime"}
)
_LAUNCH_ONLY_EXEMPT = {"run_loop.py": _LAUNCH_MARKERS}
_OPERATOR_COMMAND_MARKERS = (
    "subprocess",
    "os.system",
    "os.popen",
    "os.exec",
    "os.spawn",
    "os.startfile",
    "runtime.py",
    "tools.runtime",
    "tools/runtime",
    "--reviewer",
    "human_approved",
    "UPDATE reviews",
    "INSERT INTO reviews",
    "DELETE FROM reviews",
    "/approve",
)


def _operator_command_violations(root: Path) -> list[str]:
    """Each path:line:marker under root that could run the operator command or approve a review.

    The scan is recursive, so a nested package cannot hide one. It reads the source
    as text: a marker is reported whether it would be executed or only configured.
    """
    violations = []
    for module in sorted(root.rglob("*.py")):
        relative = module.relative_to(root).as_posix()
        exempt = _LAUNCH_ONLY_EXEMPT.get(relative, frozenset())
        for number, line in enumerate(module.read_text(encoding="utf-8").splitlines(), 1):
            for marker in _OPERATOR_COMMAND_MARKERS:
                if marker in line and marker not in exempt:
                    violations.append(f"{relative}:{number}: {marker}")
    return violations


@contextmanager
def _mock(tmp_path):
    state = tmp_path / "mock.sqlite"
    server = create_server(DEV, state, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", state
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def _operator(state, *args):
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "runtime.py"), *args, "--state", str(state)],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _decide(state, review_id, command):
    _operator(state, command, review_id, "--reviewer", "reviewer-name")


def _events(state):
    """The mock's audit, without the tool reads: the review and write events in order."""
    db = sqlite3.connect(state)
    try:
        rows = db.execute("SELECT event, case_id, detail FROM audit ORDER BY seq").fetchall()
    finally:
        db.close()
    return [(event, case_id, json.loads(detail)) for event, case_id, detail in rows]


def _write_events(state):
    return [event for event, _case, _detail in _events(state) if event != "tool_read"]


def _no_wait():
    return ToolRetry(sleep=lambda seconds: None)


def _submit(base_url, *cases):
    entries, unbuilt = submit_drafts(base_url, DEV, cases, retry=_no_wait())
    assert unbuilt == []
    return entries


def _closed_bank():
    server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    host, port = server.server_address
    server.server_close()
    return f"http://{host}:{port}"


def _pending(case_id="CARD-D01"):
    return {
        "case_id": case_id,
        "review_id": "rev_000000000000",
        "draft_hash": "0" * 64,
        "draft": {"case_id": case_id},
        "status": "pending",
        "record_id": None,
        "reason": None,
    }


def test_submit_opens_one_pending_review_per_built_draft_and_writes_no_record(tmp_path):
    with _mock(tmp_path) as (base_url, state):
        entries = _submit(base_url, "CARD-D01", "CARD-D05")
        events = _events(state)

    assert [entry["case_id"] for entry in entries] == ["CARD-D01", "CARD-D05"]
    assert all(entry["status"] == "pending" and entry["record_id"] is None for entry in entries)
    # Every built draft goes to the reviewer, whatever its routing.
    assert [entry["draft"]["routing"] for entry in entries] == ["ready_for_review", "manual_review"]
    requested = [detail for event, _case, detail in events if event == "review_requested"]
    assert [row["review_id"] for row in requested] == [entry["review_id"] for entry in entries]
    assert [row["draft_hash"] for row in requested] == [entry["draft_hash"] for entry in entries]
    assert [event for event, _case, _detail in events if event != "tool_read"] == [
        "review_requested",
        "review_requested",
    ]
    # Only the named cases' tools were read.
    assert {case for event, case, _detail in events if event == "tool_read"} == {
        "CARD-D01",
        "CARD-D05",
    }


def test_an_approved_unchanged_draft_is_recorded_once(tmp_path):
    with _mock(tmp_path) as (base_url, state):
        entries = _submit(base_url, "CARD-D01")
        _decide(state, entries[0]["review_id"], "approve")
        checked = check_reviews(base_url, entries, wait_seconds=0)
        again = check_reviews(base_url, checked, wait_seconds=0)
        events = _write_events(state)

    assert checked == [{**entries[0], "status": "recorded", "record_id": "dispute-d01"}]
    assert again == checked
    assert events == ["review_requested", "human_approved", "record_created"]


def test_a_second_approved_review_of_a_recorded_complaint_opens_no_second_record(tmp_path):
    with _mock(tmp_path) as (base_url, state):
        first = _submit(base_url, "CARD-D01")
        _decide(state, first[0]["review_id"], "approve")
        check_reviews(base_url, first, wait_seconds=0)
        second = _submit(base_url, "CARD-D01")
        _decide(state, second[0]["review_id"], "approve")
        [checked] = check_reviews(base_url, second, wait_seconds=0)
        events = _write_events(state)

    assert checked["status"] == "already_recorded"
    assert checked["record_id"] == "dispute-d01"
    assert events.count("record_created") == 1
    assert "duplicate_prevented" in events


def test_a_rejected_draft_goes_back_with_no_record(tmp_path):
    with _mock(tmp_path) as (base_url, state):
        entries = _submit(base_url, "CARD-D01")
        _decide(state, entries[0]["review_id"], "reject")
        [checked] = check_reviews(base_url, entries, wait_seconds=0)
        events = _write_events(state)

    assert checked == {**entries[0], "status": "rejected"}
    assert checked["draft"] == entries[0]["draft"]
    assert events == ["review_requested", "human_rejected"]


def test_a_draft_changed_after_submission_is_refused_before_any_write(tmp_path):
    with _mock(tmp_path) as (base_url, state):
        entries = _submit(base_url, "CARD-D01")
        _decide(state, entries[0]["review_id"], "approve")
        changed = {**entries[0], "draft": {**entries[0]["draft"], "narrative": "edited"}}
        [checked] = check_reviews(base_url, [changed], wait_seconds=0)
        events = _write_events(state)

    assert checked["status"] == "refused"
    assert checked["reason"] == "changed"
    assert events == ["review_requested", "human_approved"]


def test_an_approval_for_another_case_or_a_missing_review_writes_nothing(tmp_path):
    with _mock(tmp_path) as (base_url, state):
        [entry] = _submit(base_url, "CARD-D01")
        _decide(state, entry["review_id"], "approve")
        wrong_case = {**entry, "case_id": "CARD-D02"}
        missing = {**entry, "review_id": "rev_missing"}
        checked = check_reviews(base_url, [wrong_case, missing], wait_seconds=0)
        events = _write_events(state)

    assert [(item["status"], item["reason"]) for item in checked] == [
        ("refused", "wrong_case"),
        ("refused", "missing"),
    ]
    assert events == ["review_requested", "human_approved"]


def test_the_wait_for_a_pending_review_is_bounded(monkeypatch):
    reads = []

    def still_pending(base_url, case_id, draft, *, review_id, draft_hash):
        reads.append(review_id)
        return {"alert": "pending", "review_id": review_id, "draft_hash": draft_hash, "draft": draft}

    monkeypatch.setattr("src.review_runner.review_alert", still_pending)
    now = [0.0]

    def advance(seconds):
        now[0] += seconds

    checked = check_reviews(
        "http://unused", [_pending()], wait_seconds=5, interval=2, clock=lambda: now[0], sleep=advance
    )

    # Read at 0s, 2s, 4s and 5s, then the wait has run out.
    assert len(reads) == 4
    assert now[0] == 5
    assert checked == [_pending()]


def test_a_bank_that_cannot_be_reached_leaves_the_review_pending():
    assert check_reviews(_closed_bank(), [_pending()], wait_seconds=0) == [_pending()]


def test_a_refused_record_create_is_refused_without_retrying(monkeypatch):
    def refused(*args, **kwargs):
        raise CreateRejected(500, "upstream")

    monkeypatch.setattr("src.review_runner.review_alert", refused)

    [checked] = check_reviews("http://unused", [_pending()], wait_seconds=0)

    assert checked["status"] == "refused"
    assert checked["reason"] == "record create failed with HTTP 500: upstream"


def test_the_commands_submit_then_record_an_approved_draft(tmp_path, capsys):
    journal = tmp_path / "reviews.json"
    with _mock(tmp_path) as (base_url, state):
        main(["submit", "--base-url", base_url, "--data", str(DEV), "--journal", str(journal),
              "--case", "CARD-D01"])
        [entry] = read_journal(journal)
        submitted = capsys.readouterr().out
        _decide(state, entry["review_id"], "approve")
        main(["check", "--base-url", base_url, "--journal", str(journal), "--wait", "0"])

    assert submitted == f"CARD-D01: review {entry['review_id']} pending (ready_for_review)\n"
    assert capsys.readouterr().out == "CARD-D01: recorded as dispute-d01\n"
    assert read_journal(journal)[0]["status"] == "recorded"


def test_check_exits_1_while_a_review_is_pending_or_refused(tmp_path, capsys):
    journal = tmp_path / "reviews.json"
    with _mock(tmp_path) as (base_url, state):
        entries = _submit(base_url, "CARD-D01", "CARD-D03", "CARD-D04")
        _decide(state, entries[0]["review_id"], "reject")
        write_journal(journal, [entries[0], {**entries[1], "review_id": "rev_missing"}, entries[2]])
        with pytest.raises(SystemExit) as stopped:
            main(["check", "--base-url", base_url, "--journal", str(journal), "--wait", "0"])

    assert stopped.value.code == 1
    assert capsys.readouterr().out == (
        "CARD-D01: rejected; the draft goes back to the analyst\n"
        "CARD-D03: refused (missing); nothing was written\n"
        f"CARD-D04: review {entries[2]['review_id']} still pending\n"
    )


def test_submit_names_a_case_it_could_not_build_and_exits_1(tmp_path, capsys):
    journal = tmp_path / "reviews.json"
    with _mock(tmp_path) as (base_url, state):
        with pytest.raises(SystemExit) as stopped:
            main(["submit", "--base-url", base_url, "--data", str(DEV), "--journal", str(journal),
                  "--case", "CARD-D09"])
        events = _write_events(state)

    assert stopped.value.code == 1
    assert capsys.readouterr().err == (
        "CARD-D09: not built: the intake statement is not an exact excerpt of the intake\n"
    )
    assert read_journal(journal) == []
    assert events == []


def test_submit_reports_an_unreadable_case_list(tmp_path, capsys):
    with pytest.raises(SystemExit) as stopped:
        main(["submit", "--base-url", _closed_bank(), "--journal", str(tmp_path / "j.json")])

    assert stopped.value.code == 1
    assert capsys.readouterr().err == "the bank case list could not be read\n"
    assert not (tmp_path / "j.json").exists()


def test_submit_reports_a_review_it_could_not_open(tmp_path, capsys, monkeypatch):
    def refused(base_url, case_id, draft):
        raise ReviewRefused(500, "submit_failed")

    monkeypatch.setattr("src.review_runner.submit_review", refused)
    with _mock(tmp_path) as (base_url, _state), pytest.raises(SystemExit) as stopped:
        main(["submit", "--base-url", base_url, "--data", str(DEV),
              "--journal", str(tmp_path / "j.json"), "--case", "CARD-D01"])

    assert stopped.value.code == 1
    assert capsys.readouterr().err == "a review could not be opened: submit_failed\n"


def test_running_the_module_checks_the_default_journal(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write_journal(tmp_path / "reports" / "reviews.json", [])
    monkeypatch.setattr(sys, "argv", ["review_runner", "check", "--wait", "0"])

    runpy.run_path(str(ROOT / "src" / "review_runner.py"), run_name="__main__")

    assert capsys.readouterr().out == ""


def test_nothing_under_src_runs_the_operator_command_or_approves_a_review():
    # The gate is manual only if the application cannot reach the operator command
    # and cannot approve a review itself. The audit repeats this check.
    assert _operator_command_violations(ROOT / "src") == []


def test_the_guard_flags_a_module_that_runs_the_operator_command(tmp_path):
    package = tmp_path / "src" / "gate"
    package.mkdir(parents=True)
    (package / "shortcut.py").write_text(
        "import subprocess\n\n"
        'subprocess.run(["python", "tools/runtime.py", "approve", "rev_1"], check=True)\n',
        encoding="utf-8",
    )

    violations = _operator_command_violations(tmp_path / "src")

    # Both the import and the call are reported, from a nested module: the scan
    # recurses and does not look at the top level only.
    assert violations == [
        "gate/shortcut.py:1: subprocess",
        "gate/shortcut.py:3: subprocess",
        "gate/shortcut.py:3: runtime.py",
        "gate/shortcut.py:3: tools/runtime",
    ]


def test_the_guard_flags_a_module_that_approves_a_review_itself(tmp_path):
    package = tmp_path / "src"
    package.mkdir()
    (package / "auto.py").write_text(
        'db.execute("UPDATE reviews SET status = ?", ("approved",))\n',
        encoding="utf-8",
    )
    (package / "endpoint.py").write_text(
        'http.request("POST", "/approve", body)\n',
        encoding="utf-8",
    )

    violations = _operator_command_violations(tmp_path / "src")

    assert violations == [
        "auto.py:1: UPDATE reviews",
        "endpoint.py:1: /approve",
    ]


def test_the_guard_allows_the_word_approved_where_a_person_decided(tmp_path):
    package = tmp_path / "src"
    package.mkdir()
    (package / "gate.py").write_text(
        'if row.status == "approved":\n    record(draft)\n',
        encoding="utf-8",
    )

    # Reading the bank's record of a person's decision is the gate working, not a
    # bypass, so it must not be flagged.
    assert _operator_command_violations(tmp_path / "src") == []


def test_the_launch_exemption_for_run_loop_does_not_hide_an_approval_marker(tmp_path):
    package = tmp_path / "src"
    package.mkdir()
    source = (ROOT / "src" / "run_loop.py").read_text(encoding="utf-8")
    target = package / "run_loop.py"
    target.write_text(source, encoding="utf-8")

    # The loop starts the supplied mock, so its own process-launch markers are
    # allowed. It must still be flagged the moment it names an approval path.
    assert _operator_command_violations(package) == []

    for marker in ("--reviewer", "/approve", "UPDATE reviews"):
        target.write_text(source + f"\nOPERATOR = {marker}\n", encoding="utf-8")
        violations = _operator_command_violations(package)
        assert violations == [f"run_loop.py:{len(source.splitlines()) + 2}: {marker}"], marker
