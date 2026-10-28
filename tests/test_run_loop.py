"""The one-command loop: port choice, state default, readiness, scoring and shutdown.

run_loop is checked with a fake ProcessRunner and a fake HealthProbe: the tests
assert the argv handed to the supplied mock and to the scored run, the health URL
and timeout, the numbers read back from the report, and that the mock is stopped
on every path. One test runs the real adapters against the supplied runtime on a
free port and scores all twelve dev cases; the other stops a child through the real
adapter.
"""

import json
import runpy
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

import pytest

from src import run_loop as loop
from src.run_loop import (
    HttpHealthProbe,
    LoopError,
    LoopResult,
    _display_path,
    default_state_path,
    main,
    run_loop,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "dev"
GOLD = ROOT / "feedback" / "dev_gold.json"
REPORT = {
    "pass_count": 11,
    "total_cases": 12,
    "p50_latency_ms": 31,
    "p95_latency_ms": 3444,
}


class _Process:
    """One fake child: a running mock, or a scored run that has already exited."""

    def __init__(self, exit_code):
        self._exit_code = exit_code
        self.terminated = 0
        self.killed = 0
        self.wait_timeouts = []

    def poll(self):
        return self._exit_code

    def terminate(self):
        self.terminated += 1
        self._exit_code = 0

    def kill(self):
        self.killed += 1
        self._exit_code = 0

    def wait(self, timeout):
        self.wait_timeouts.append(timeout)
        return self._exit_code or 0


class _HangingProcess(_Process):
    """One fake child that only ends after it is killed."""

    def __init__(self):
        super().__init__(None)
        self.waits = 0

    def wait(self, timeout):
        self.wait_timeouts.append(timeout)
        self.waits += 1
        if self.waits == 1:
            raise subprocess.TimeoutExpired(cmd="mock", timeout=timeout)
        return 1


class _Runner:
    """The fake ProcessRunner: records argv, keeps the mock up, writes the report."""

    def __init__(
        self, *, scored_exit=0, mock_exit=None, mock_process=None,
        write_report=True, report_text=None,
    ):
        self.scored_exit = scored_exit
        self.mock_exit = mock_exit
        self.mock_process = mock_process
        self.write_report = write_report
        self.report_text = report_text
        self.starts = []
        self.processes = []

    def start(self, argv):
        argv = list(argv)
        self.starts.append(argv)
        if any(Path(part).name == "scored_run.py" for part in argv):
            process = _Process(self.scored_exit)
            if self.write_report:
                target = Path(_flag(argv, "--report"))
                text = self.report_text
                target.write_text(
                    json.dumps(REPORT) if text is None else text, encoding="utf-8"
                )
        else:
            process = (
                self.mock_process
                if self.mock_process is not None
                else _Process(self.mock_exit)
            )
        self.processes.append(process)
        return process


class _Probe:
    """The fake HealthProbe: answers after the deadline, or immediately."""

    def __init__(self, ready=True):
        self.ready = ready
        self.calls = []

    def wait_ready(self, base_url, timeout):
        self.calls.append((base_url, timeout))
        return self.ready


def _flag(argv, name):
    return argv[argv.index(name) + 1]


def _run_loop(tmp_path, *, runner, probe, **overrides):
    kwargs = {
        "data_dir": DATA,
        "gold": GOLD,
        "port": 8794,
        "state_path": tmp_path / "state.sqlite",
        "report_path": tmp_path / "scored-run.json",
        "meter_path": tmp_path / "meters.jsonl",
        "markdown_path": tmp_path / "scored-run.md",
        "submission_path": tmp_path / "submission.json",
    }
    kwargs.update(overrides)
    return run_loop(runner=runner, probe=probe, **kwargs)


def test_the_loop_creates_missing_parent_directories(tmp_path):
    """A clean checkout has no .state or submissions, so the loop makes them."""
    fresh = tmp_path / "fresh"
    runner = _Runner()

    result = _run_loop(
        tmp_path,
        runner=runner,
        probe=_Probe(),
        state_path=fresh / "state.sqlite",
        report_path=fresh / "reports" / "scored-run.json",
        meter_path=fresh / "reports" / "meters.jsonl",
        markdown_path=fresh / "reports" / "scored-run.md",
        submission_path=fresh / "submissions" / "submission.json",
    )

    for path in (
        result.state_path,
        result.report_path,
        result.meter_path,
        (fresh / "reports" / "scored-run.md").resolve(),
        (fresh / "submissions" / "submission.json").resolve(),
    ):
        assert path.parent.is_dir(), path.parent


def test_the_loop_starts_the_mock_waits_for_health_scores_and_stops(tmp_path):
    runner = _Runner()
    probe = _Probe()

    result = _run_loop(tmp_path, runner=runner, probe=probe)

    mock_argv, scored_argv = runner.starts
    assert Path(mock_argv[1]) == ROOT / "tools" / "runtime.py"
    assert mock_argv[2] == "serve"
    assert _flag(mock_argv, "--data") == str(DATA)
    assert _flag(mock_argv, "--port") == "8794"
    assert _flag(mock_argv, "--state") == str((tmp_path / "state.sqlite").resolve())
    assert probe.calls == [("http://127.0.0.1:8794", 30.0)]
    assert Path(scored_argv[1]) == ROOT / "tools" / "scored_run.py"
    assert _flag(scored_argv, "--base-url") == "http://127.0.0.1:8794"
    assert _flag(scored_argv, "--data") == str(DATA)
    assert _flag(scored_argv, "--gold") == str(GOLD)
    assert _flag(scored_argv, "--submission") == str(
        (tmp_path / "submission.json").resolve()
    )
    assert _flag(scored_argv, "--report") == str((tmp_path / "scored-run.json").resolve())
    assert _flag(scored_argv, "--meters") == str(
        (tmp_path / "scored-run-meters.json").resolve()
    )
    assert _flag(scored_argv, "--markdown") == str(
        (tmp_path / "scored-run.md").resolve()
    )
    assert _flag(scored_argv, "--case-meters") == str(
        (tmp_path / "meters.jsonl").resolve()
    )
    mock, scored = runner.processes
    assert mock.terminated == 1
    assert scored.terminated == 0
    assert result == LoopResult(
        port=8794,
        state_path=(tmp_path / "state.sqlite").resolve(),
        passed=11,
        total=12,
        p50_ms=31.0,
        p95_ms=3444.0,
        report_path=(tmp_path / "scored-run.json").resolve(),
        meter_path=(tmp_path / "meters.jsonl").resolve(),
        exit_code=0,
    )


def test_a_loop_without_a_port_or_state_picks_a_free_port_and_names_state_after_it(
    tmp_path,
):
    runner = _Runner()

    result = _run_loop(tmp_path, runner=runner, probe=_Probe(), port=None, state_path=None)

    chosen = int(_flag(runner.starts[0], "--port"))
    assert result.port == chosen
    assert 0 < chosen < 65536
    assert result.state_path == (
        Path.cwd() / ".state" / f"loop-{chosen}.sqlite"
    ).resolve()
    assert _flag(runner.starts[0], "--state") == str(result.state_path)


def test_the_default_state_path_is_named_after_the_port():
    assert default_state_path(8794) == Path(".state") / "loop-8794.sqlite"
    assert default_state_path(8794) != default_state_path(8795)


def test_a_mock_that_never_answers_health_fails_with_the_url_and_timeout_and_is_stopped(
    tmp_path,
):
    runner = _Runner()

    with pytest.raises(LoopError) as failed:
        _run_loop(
            tmp_path, runner=runner, probe=_Probe(ready=False), health_timeout=2.5
        )

    message = str(failed.value)
    assert "http://127.0.0.1:8794" in message
    assert "2.5" in message
    assert len(runner.starts) == 1
    assert runner.processes[0].terminated == 1


def test_a_mock_that_already_exited_is_waited_for_but_not_terminated_again(tmp_path):
    runner = _Runner(mock_exit=1)

    result = _run_loop(tmp_path, runner=runner, probe=_Probe())

    mock, scored = runner.processes
    assert mock.terminated == 0
    assert mock.killed == 0
    assert mock.wait_timeouts == [5.0]
    assert scored.terminated == 0
    assert result.exit_code == 0


def test_a_mock_that_ignores_terminate_is_killed_and_the_loop_error_survives(tmp_path):
    mock = _HangingProcess()
    runner = _Runner(mock_process=mock)

    with pytest.raises(LoopError) as failed:
        _run_loop(tmp_path, runner=runner, probe=_Probe(ready=False))

    assert "did not answer GET /health" in str(failed.value)
    assert mock.terminated == 1
    assert mock.killed == 1
    assert mock.wait_timeouts == [5.0, 5.0]


def test_the_process_adapter_kills_a_child_and_waits_for_it():
    runner = loop.SubprocessRunner()
    process = runner.start([sys.executable, "-c", "import time; time.sleep(30)"])

    assert process.poll() is None
    process.kill()
    assert process.wait(timeout=10.0) != 0


def test_a_failing_case_is_data_not_a_loop_error(tmp_path):
    result = _run_loop(
        tmp_path, runner=_Runner(scored_exit=1), probe=_Probe()
    )

    assert (result.passed, result.total, result.exit_code) == (11, 12, 1)


def test_a_scored_run_that_writes_no_report_is_a_loop_error(tmp_path):
    runner = _Runner(scored_exit=1, write_report=False)

    with pytest.raises(LoopError) as failed:
        _run_loop(tmp_path, runner=runner, probe=_Probe())

    assert str((tmp_path / "scored-run.json").resolve()) in str(failed.value)
    assert runner.processes[0].terminated == 1


def test_a_report_that_is_not_json_is_a_loop_error(tmp_path):
    runner = _Runner(report_text="{")

    with pytest.raises(LoopError) as failed:
        _run_loop(tmp_path, runner=runner, probe=_Probe())

    assert "readable report" in str(failed.value)


def test_a_report_without_a_pass_count_is_a_loop_error_not_a_key_error(tmp_path):
    runner = _Runner(report_text='{"total_cases": 12}')

    with pytest.raises(LoopError) as failed:
        _run_loop(tmp_path, runner=runner, probe=_Probe())

    assert "readable report" in str(failed.value)
    assert "pass_count" in str(failed.value)


def test_a_report_with_a_non_numeric_latency_is_a_loop_error(tmp_path):
    runner = _Runner(
        report_text='{"pass_count": 11, "total_cases": 12, "p50_latency_ms": "fast"}'
    )

    with pytest.raises(LoopError) as failed:
        _run_loop(tmp_path, runner=runner, probe=_Probe())

    assert "readable report" in str(failed.value)
    assert "fast" in str(failed.value)


def test_the_real_probe_retries_until_the_deadline(monkeypatch):
    clock = iter([0.0, 0.5, 2.0])
    slept = []

    def refused(url, timeout):
        raise ConnectionRefusedError(url)

    monkeypatch.setattr(loop.urllib.request, "urlopen", refused)
    monkeypatch.setattr(loop.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(loop.time, "sleep", slept.append)

    assert HttpHealthProbe().wait_ready("http://127.0.0.1:9", 1.0) is False
    assert slept == [0.1]


def test_a_report_inside_the_repository_is_named_relative_to_it():
    assert _display_path(ROOT / "reports" / "scored-run.json") == (
        "reports/scored-run.json"
    )
    outside = ROOT.parent / "elsewhere.json"
    assert _display_path(outside) == str(outside)


def _result(tmp_path):
    return LoopResult(
        port=8794,
        state_path=(tmp_path / "state.sqlite").resolve(),
        passed=11,
        total=12,
        p50_ms=31.0,
        p95_ms=3444.0,
        report_path=(tmp_path / "scored-run.json").resolve(),
        meter_path=(tmp_path / "meters.jsonl").resolve(),
        exit_code=0,
    )


def test_the_command_falls_back_to_the_environment(tmp_path, monkeypatch):
    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return _result(tmp_path)

    monkeypatch.setattr(loop, "run_loop", fake)
    monkeypatch.setenv("DISPUTE_PORT", "8795")
    monkeypatch.setenv("DISPUTE_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("DISPUTE_STATE", str(tmp_path / "env.sqlite"))

    assert main([]) == 0
    assert seen["port"] == 8795
    assert seen["data_dir"] == tmp_path / "data"
    assert seen["state_path"] == tmp_path / "env.sqlite"


def test_the_flag_wins_over_the_environment(tmp_path, monkeypatch):
    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return _result(tmp_path)

    monkeypatch.setattr(loop, "run_loop", fake)
    monkeypatch.setenv("DISPUTE_PORT", "8795")
    monkeypatch.setenv("DISPUTE_DATA", str(tmp_path / "env-data"))
    monkeypatch.setenv("DISPUTE_STATE", str(tmp_path / "env.sqlite"))

    status = main(
        [
            "--port", "8796",
            "--data", str(tmp_path / "flag-data"),
            "--state", str(tmp_path / "flag.sqlite"),
        ]
    )

    assert status == 0
    assert seen["port"] == 8796
    assert seen["data_dir"] == tmp_path / "flag-data"
    assert seen["state_path"] == tmp_path / "flag.sqlite"


def test_the_command_uses_no_environment_when_the_variables_are_unset(
    tmp_path, monkeypatch
):
    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return _result(tmp_path)

    monkeypatch.setattr(loop, "run_loop", fake)
    for name in ("DISPUTE_PORT", "DISPUTE_DATA", "DISPUTE_STATE"):
        monkeypatch.delenv(name, raising=False)

    assert main([]) == 0
    assert seen["port"] is None
    assert seen["data_dir"] == ROOT / "data" / "dev"
    assert seen["state_path"] is None


def test_a_dispute_port_that_is_not_a_number_is_a_clear_error(monkeypatch, capsys):
    called = []
    monkeypatch.setattr(loop, "run_loop", lambda **kwargs: called.append(kwargs))
    monkeypatch.setenv("DISPUTE_PORT", "not-a-port")

    assert main([]) == 1
    assert called == []
    assert capsys.readouterr().err == (
        "DISPUTE_PORT must be a whole number, not 'not-a-port'\n"
    )


def test_the_command_prints_one_summary_line_and_exits_zero(tmp_path, monkeypatch, capsys):
    outside = ROOT.parent / "elsewhere" / "scored-run.json"
    result = LoopResult(
        port=8794,
        state_path=(tmp_path / "state.sqlite").resolve(),
        passed=11,
        total=12,
        p50_ms=31.0,
        p95_ms=3444.0,
        report_path=outside,
        meter_path=(tmp_path / "meters.jsonl").resolve(),
        exit_code=0,
    )
    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return result

    monkeypatch.setattr(loop, "run_loop", fake)

    status = main(
        [
            "--data", str(DATA),
            "--gold", str(GOLD),
            "--port", "8794",
            "--state", str(tmp_path / "state.sqlite"),
            "--report", str(outside),
            "--case-meters", str(tmp_path / "meters.jsonl"),
            "--markdown", str(tmp_path / "scored-run.md"),
            "--submission", str(tmp_path / "submission.json"),
        ]
    )

    assert status == 0
    assert seen["port"] == 8794
    assert seen["health_timeout"] == 30.0
    assert seen["data_dir"] == DATA
    assert seen["gold"] == GOLD
    assert capsys.readouterr().out == (
        "11 / 12 cases passed; p50 31.000 ms; p95 3444.000 ms; report "
        + str(outside)
        + "; meters "
        + loop._display_path(tmp_path / "meters.jsonl")
        + "\n"
    )


def test_the_command_exits_one_when_the_loop_fails(tmp_path, monkeypatch, capsys):
    def broken(**kwargs):
        raise LoopError("the mock at http://127.0.0.1:8794 did not answer GET /health")

    monkeypatch.setattr(loop, "run_loop", broken)

    status = main(
        [
            "--port", "8794",
            "--state", str(tmp_path / "state.sqlite"),
            "--report", str(tmp_path / "scored-run.json"),
            "--case-meters", str(tmp_path / "meters.jsonl"),
            "--markdown", str(tmp_path / "scored-run.md"),
            "--submission", str(tmp_path / "submission.json"),
        ]
    )

    assert status == 1
    assert capsys.readouterr().err == (
        "the mock at http://127.0.0.1:8794 did not answer GET /health\n"
    )


def test_the_module_can_be_run_as_a_script(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["run_loop.py", "--port", "not-a-port"])

    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(ROOT / "src" / "run_loop.py"), run_name="__main__")

    assert exited.value.code == 2
    assert "invalid int value" in capsys.readouterr().err


def test_the_loop_runs_the_supplied_runtime_and_scores_twelve_cases(tmp_path):
    port = _free_port()

    result = run_loop(
        data_dir=DATA,
        gold=GOLD,
        port=port,
        state_path=tmp_path / "state.sqlite",
        report_path=tmp_path / "scored-run.json",
        meter_path=tmp_path / "meters.jsonl",
        markdown_path=tmp_path / "scored-run.md",
        submission_path=tmp_path / "submission.json",
    )

    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert result.port == port
    assert (result.passed, result.total) == (12, 12)
    assert report["total_cases"] == 12
    assert len(report["cases"]) == 12
    assert result.p50_ms is not None
    assert result.p95_ms is not None
    assert result.exit_code == (0 if result.passed == result.total else 1)
    # Windows can reset the connection while the mock's socket closes, so any
    # OS-level failure counts as "the mock is gone"; a successful answer does not.
    assert not _health_answers(port)


def _health_answers(port: int) -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{port}/health", timeout=1):
            return True
    except OSError:
        return False


def _free_port():
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]
