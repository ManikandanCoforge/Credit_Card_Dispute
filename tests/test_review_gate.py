"""A finished draft is submitted, and an approval is the alert to record it."""

import json
import sqlite3
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest

from src.review_gate import ReviewRefused, review_alert, submit_review
from tools.runtime import create_server

ROOT = Path(__file__).resolve().parents[1]
_DRAFT = {"case_id": "CARD-D01", "summary": "Human-reviewed draft"}
_HASH = "02547bcd27f66f512dc374b01b1e36687ecd2ebee6172e49642f0a25623f89a6"


@contextmanager
def _bank(tmp_path):
    state = tmp_path / "mock.sqlite"
    server = create_server(ROOT / "data" / "dev", state, port=0)
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


def _audit(state):
    return json.loads(_operator(state, "audit"))


def _audit_events(state):
    return [row["event"] for row in _audit(state)]


def _detail(state, event):
    row = next(item for item in _audit(state) if item["event"] == event)
    return json.loads(row["detail"])


def _revise(state, sql):
    with sqlite3.connect(state) as db:
        db.execute(sql)


def _decide(state, review_id, command):
    _operator(state, command, review_id, "--reviewer", "reviewer-name")


def _alert(base_url, draft, submitted):
    return review_alert(
        base_url,
        "CARD-D01",
        draft,
        review_id=submitted["review_id"],
        draft_hash=submitted["draft_hash"],
        submission_reference="dispute-d01",
    )


def _get(base_url, path):
    from http.client import HTTPConnection
    from urllib.parse import urlparse

    origin = urlparse(base_url)
    connection = HTTPConnection(origin.hostname, origin.port)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        status = response.status
        response.read()
    finally:
        connection.close()
    return status


def test_submitting_a_finished_draft_returns_without_a_record(tmp_path):
    with _bank(tmp_path) as (base_url, state):
        submitted = submit_review(base_url, "CARD-D01", dict(_DRAFT))
        requested = _detail(state, "review_requested")
        assert submitted == {
            "review_id": requested["review_id"],
            "draft_hash": _HASH,
            "draft": _DRAFT,
            "status": "pending",
        }
        assert requested["draft_hash"] == _HASH
        assert _get(base_url, "/v1/records/CARD-D01") == 404
        assert "record_created" not in _audit_events(state)


def test_an_approval_alerts_that_the_record_was_submitted(tmp_path):
    with _bank(tmp_path) as (base_url, state):
        draft = dict(_DRAFT)
        submitted = submit_review(base_url, "CARD-D01", draft)
        _decide(state, submitted["review_id"], "approve")
        alert = _alert(base_url, draft, submitted)
        assert alert == {
            "alert": "submit_record",
            "review_id": submitted["review_id"],
            "draft_hash": _HASH,
            "draft": _DRAFT,
            "record_id": "dispute-d01",
            "created": True,
        }
        assert _get(base_url, "/v1/records/CARD-D01") == 200
        events = _audit_events(state)
        assert "human_approved" in events
        assert "record_created" in events
        assert "unapproved_write_attempt" not in events


def test_a_rejection_returns_the_draft_and_creates_no_record(tmp_path):
    with _bank(tmp_path) as (base_url, state):
        draft = dict(_DRAFT)
        submitted = submit_review(base_url, "CARD-D01", draft)
        _decide(state, submitted["review_id"], "reject")
        alert = _alert(base_url, draft, submitted)
        assert alert == {
            "alert": "rejected",
            "review_id": submitted["review_id"],
            "draft_hash": _HASH,
            "draft": _DRAFT,
        }
        assert _get(base_url, "/v1/records/CARD-D01") == 404
        events = _audit_events(state)
        assert "human_rejected" in events
        assert "record_created" not in events
        assert "unapproved_write_attempt" not in events


def test_a_pending_review_returns_without_waiting(tmp_path):
    with _bank(tmp_path) as (base_url, state):
        draft = dict(_DRAFT)
        submitted = submit_review(base_url, "CARD-D01", draft)
        alert = _alert(base_url, draft, submitted)
        assert alert["alert"] == "pending"
        assert _get(base_url, "/v1/records/CARD-D01") == 404
        assert "record_created" not in _audit_events(state)


def test_a_changed_draft_is_refused_and_creates_no_record(tmp_path):
    draft = dict(_DRAFT)
    with _bank(tmp_path) as (base_url, state):
        submitted = submit_review(base_url, "CARD-D01", draft)
        draft["summary"] = "edited after review"
        with pytest.raises(ReviewRefused) as raised:
            _alert(base_url, draft, submitted)
        assert raised.value.status == 403
        assert _get(base_url, "/v1/records/CARD-D01") == 404
        events = _audit_events(state)
        assert "record_created" not in events
        assert "unapproved_write_attempt" not in events


def test_a_review_whose_stored_hash_changed_is_refused(tmp_path):
    with _bank(tmp_path) as (base_url, state):
        draft = dict(_DRAFT)
        submitted = submit_review(base_url, "CARD-D01", draft)
        _revise(state, "UPDATE reviews SET hash = 'changed'")
        with pytest.raises(ReviewRefused) as raised:
            _alert(base_url, draft, submitted)
        assert raised.value.status == 403
        assert _get(base_url, "/v1/records/CARD-D01") == 404
        assert "unapproved_write_attempt" not in _audit_events(state)


def test_a_missing_review_stops_without_a_record(tmp_path):
    with _bank(tmp_path) as (base_url, state):
        draft = dict(_DRAFT)
        submitted = submit_review(base_url, "CARD-D01", draft)
        _revise(state, "DELETE FROM reviews")
        with pytest.raises(ReviewRefused) as raised:
            _alert(base_url, draft, submitted)
        assert raised.value.reason == "missing"
        assert _get(base_url, "/v1/records/CARD-D01") == 404


def test_an_unknown_decision_stops_without_a_record(tmp_path):
    with _bank(tmp_path) as (base_url, state):
        draft = dict(_DRAFT)
        submitted = submit_review(base_url, "CARD-D01", draft)
        _revise(state, "UPDATE reviews SET status = 'held'")
        with pytest.raises(ReviewRefused) as raised:
            _alert(base_url, draft, submitted)
        assert raised.value.reason == "unknown"
        assert _get(base_url, "/v1/records/CARD-D01") == 404


def test_a_wrong_case_approval_stops_without_a_record(tmp_path):
    with _bank(tmp_path) as (base_url, state):
        draft = dict(_DRAFT)
        submitted = submit_review(base_url, "CARD-D01", draft)
        _revise(state, "UPDATE reviews SET case_id = 'CARD-D02', status = 'approved'")
        with pytest.raises(ReviewRefused) as raised:
            _alert(base_url, draft, submitted)
        assert raised.value.reason == "wrong_case"
        assert _get(base_url, "/v1/records/CARD-D01") == 404
        assert "record_created" not in _audit_events(state)


def test_a_second_approval_returns_the_stored_record(tmp_path):
    with _bank(tmp_path) as (base_url, state):
        first_draft = dict(_DRAFT)
        first = submit_review(base_url, "CARD-D01", first_draft)
        _decide(state, first["review_id"], "approve")
        first_alert = _alert(base_url, first_draft, first)
        second_draft = dict(_DRAFT)
        second = submit_review(base_url, "CARD-D01", second_draft)
        _decide(state, second["review_id"], "approve")
        second_alert = _alert(base_url, second_draft, second)
        assert first_alert["record_id"] == "dispute-d01"
        assert first_alert["created"] is True
        assert second_alert["alert"] == "submit_record"
        assert second_alert["record_id"] == "dispute-d01"
        assert second_alert["created"] is False


def test_a_rejected_submission_does_not_open_a_review(tmp_path):
    draft = {"case_id": "CARD-D02", "summary": "Human-reviewed draft"}
    with _bank(tmp_path) as (base_url, state):
        with pytest.raises(ReviewRefused) as raised:
            submit_review(base_url, "CARD-D01", draft)
        assert raised.value.status == 400
        assert json.loads(_operator(state, "pending")) == []
        assert "review_requested" not in _audit_events(state)


def test_an_unreachable_bank_does_not_open_a_review():
    with pytest.raises(ReviewRefused) as raised:
        submit_review("http://127.0.0.1:1", "CARD-D01", dict(_DRAFT))
    assert raised.value.status is None
    assert raised.value.reason == "unreachable"


def test_an_origin_without_a_host_is_unreachable():
    with pytest.raises(ReviewRefused) as raised:
        submit_review("http://", "CARD-D01", dict(_DRAFT))
    assert raised.value.reason == "unreachable"
