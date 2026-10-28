"""Run the whole demo loop in one command.

The loop makes the output directories, takes the port and the data and state paths
from their flags or from DISPUTE_PORT, DISPUTE_DATA and DISPUTE_STATE, starts the
supplied mock (tools/runtime.py) with a state file of its own, waits for GET /health,
runs tools/scored_run.py against that mock, reads the report the scored run wrote,
and stops the mock. A case that fails is data, not a loop failure: the command exits
0 whenever the run completed. It exits 1 only when the mock never answered or the
scored run left no readable report.

  python -m src.run_loop

The scored run's JSON meter rows are written beside its report, named after the
report with a -meters suffix. The defaults are the committed paths, so a trial run
passes --report, --case-meters, --markdown and --submission to point all four at a
scratch directory and leave the committed artifacts alone.
"""

import argparse
import contextlib
import json
import os
import socket
import subprocess  # nosec B404
import sys
import time
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "tools" / "runtime.py"
SCORED_RUN = ROOT / "tools" / "scored_run.py"


class RunningProcess(Protocol):
    """The part of a child process the loop uses: ask, stop, and wait for it."""

    def poll(self) -> int | None:
        """Return the exit status, or None while the child is still running."""
        ...

    def terminate(self) -> None:
        """Ask the child to stop, the way SIGTERM does."""
        ...

    def kill(self) -> None:
        """Stop the child at once, the way SIGKILL does."""
        ...

    def wait(self, timeout: float) -> int:
        """Block until the child exits or the timeout expires, and return its status."""
        ...


class ProcessRunner(Protocol):
    """Start one child process and hand back a handle to it."""

    def start(self, argv: Sequence[str]) -> RunningProcess:
        """Start one child for a fixed argv and return it running."""
        ...


class _PopenProcess:
    """Wrap one Popen so the loop sees only poll, terminate and wait."""

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self._process = process

    def poll(self) -> int | None:
        return self._process.poll()

    def terminate(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()

    def kill(self) -> None:
        if self._process.poll() is None:
            self._process.kill()

    def wait(self, timeout: float) -> int:
        return self._process.wait(timeout=timeout)


class SubprocessRunner:
    """The real process adapter: subprocess.Popen with a fixed argv, never a shell."""

    def start(self, argv: Sequence[str]) -> RunningProcess:
        """Start the command and return the running child."""
        # Fixed argv built by the loop, never a shell.
        process = subprocess.Popen(list(argv))  # nosec B603
        return _PopenProcess(process)


class HealthProbe(Protocol):
    """Report whether the mock answers GET /health before the deadline."""

    def wait_ready(self, base_url: str, timeout: float) -> bool:
        """Return True once GET /health answers, or False when the timeout expires."""
        ...


class HttpHealthProbe:
    """The real probe: urllib.request against GET /health until it answers."""

    def wait_ready(self, base_url: str, timeout: float) -> bool:
        """Poll GET /health until it answers, and report whether it did."""
        deadline = time.monotonic() + timeout
        while True:
            try:
                # base_url is the loopback mock on the port the loop chose.
                with urllib.request.urlopen(  # nosec B310
                    f"{base_url}/health", timeout=1
                ):
                    return True
            except OSError:
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.1)


_DEFAULT_RUNNER: ProcessRunner = SubprocessRunner()
_DEFAULT_PROBE: HealthProbe = HttpHealthProbe()


class LoopError(RuntimeError):
    """The loop could not finish: the mock never answered or no report was written."""


@dataclass(frozen=True)
class LoopResult:
    """What one completed loop measured and wrote."""

    port: int
    state_path: Path
    passed: int
    total: int
    p50_ms: float | None
    p95_ms: float | None
    report_path: Path
    meter_path: Path
    exit_code: int


def default_state_path(port: int) -> Path:
    """The state file a loop uses when the caller names none, unique per port."""
    return Path(".state") / f"loop-{port}.sqlite"


def free_port() -> int:
    """Ask the operating system for a free loopback port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _stop(process: RunningProcess, child_timeout: float) -> None:
    """Stop a child: terminate, wait a short grace, then kill it if it is still there."""
    if process.poll() is None:
        process.terminate()
    grace = min(child_timeout, 5.0)
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=grace)


def run_loop(
    *,
    data_dir: Path,
    gold: Path,
    port: int | None = None,
    state_path: Path | None = None,
    report_path: Path,
    meter_path: Path,
    markdown_path: Path,
    submission_path: Path,
    runner: ProcessRunner = _DEFAULT_RUNNER,
    probe: HealthProbe = _DEFAULT_PROBE,
    health_timeout: float = 30.0,
    child_timeout: float = 300.0,
) -> LoopResult:
    """Run the mock, the scored run and the report read as one loop.

    Args:
        data_dir: The dataset directory the mock serves and the run scores.
        gold: The development answers the run compares against.
        port: The port to use, or None to ask the operating system for a free one.
        state_path: The mock's state file, or None for .state/loop-<port>.sqlite.
        report_path: Where the scored run writes its JSON report.
        meter_path: Where the scored run writes one meter line per case.
        markdown_path: Where the scored run writes its readable report.
        submission_path: Where the scored run writes its evaluator array.
        runner: Starts the mock and the scored run. Tests pass a fake.
        probe: Waits for GET /health. Tests pass a fake.
        health_timeout: Seconds to wait for the mock to answer /health.
        child_timeout: Seconds to wait for a child when it is scored or stopped.

    Returns:
        The port, state file, numbers and paths of the completed run.

    Raises:
        LoopError: The mock never answered, or the run wrote no readable report.

    The state, report, meter, markdown and submission parents are created first,
    so a clean checkout with no .state or submissions directory runs as well as a
    used one.
    """
    chosen = port if port is not None else free_port()
    state = (
        state_path if state_path is not None else default_state_path(chosen)
    ).resolve()
    data = data_dir.resolve()
    gold_path = gold.resolve()
    report = report_path.resolve()
    meter = meter_path.resolve()
    markdown = markdown_path.resolve()
    submission = submission_path.resolve()
    base_url = f"http://127.0.0.1:{chosen}"

    for target in (state, report, meter, markdown, submission):
        target.parent.mkdir(parents=True, exist_ok=True)

    mock = runner.start(
        [
            sys.executable,
            str(RUNTIME),
            "serve",
            "--data",
            str(data),
            "--state",
            str(state),
            "--port",
            str(chosen),
        ]
    )
    try:
        if not probe.wait_ready(base_url, health_timeout):
            raise LoopError(
                f"the mock at {base_url} did not answer GET /health within "
                f"{health_timeout} seconds; start it by hand to see its error"
            )
        exit_code = _run_scored(
            runner,
            base_url=base_url,
            data=data,
            gold=gold_path,
            submission=submission,
            report=report,
            meter=meter,
            markdown=markdown,
            child_timeout=child_timeout,
        )
        passed, total, p50_ms, p95_ms = _read_report(report)
    finally:
        _stop(mock, child_timeout)

    return LoopResult(
        port=chosen,
        state_path=state,
        passed=passed,
        total=total,
        p50_ms=p50_ms,
        p95_ms=p95_ms,
        report_path=report,
        meter_path=meter,
        exit_code=exit_code,
    )


def _run_scored(
    runner: ProcessRunner,
    *,
    base_url: str,
    data: Path,
    gold: Path,
    submission: Path,
    report: Path,
    meter: Path,
    markdown: Path,
    child_timeout: float,
) -> int:
    """Start the scored run against the mock and return its exit status."""
    meters = report.with_name(f"{report.stem}-meters.json")
    process = runner.start(
        [
            sys.executable,
            str(SCORED_RUN),
            "--base-url",
            base_url,
            "--data",
            str(data),
            "--gold",
            str(gold),
            "--submission",
            str(submission),
            "--report",
            str(report),
            "--meters",
            str(meters),
            "--markdown",
            str(markdown),
            "--case-meters",
            str(meter),
        ]
    )
    return process.wait(timeout=child_timeout)


def _read_report(path: Path) -> tuple[int, int, float | None, float | None]:
    """Read the pass count, case count and latencies, or raise LoopError naming the path."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        passed = int(data["pass_count"])
        total = int(data["total_cases"])
    except (OSError, TypeError, ValueError, KeyError) as error:
        raise LoopError(
            f"the scored run did not write a readable report at {path}: {error}"
        ) from error
    p50 = data.get("p50_latency_ms")
    p95 = data.get("p95_latency_ms")
    try:
        p50_ms = None if p50 is None else float(p50)
        p95_ms = None if p95 is None else float(p95)
    except (TypeError, ValueError) as error:
        raise LoopError(
            f"the scored run did not write a readable report at {path}: {error}"
        ) from error
    return passed, total, p50_ms, p95_ms


def _format_ms(value: float | None) -> str:
    """Render one latency in milliseconds, or n/a when there was none."""
    return "n/a" if value is None else f"{value:.3f}"


def _display_path(path: Path) -> str:
    """Name a path relative to the repository when it is inside it."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _summary_line(result: LoopResult) -> str:
    """The one line a completed loop prints: cases, latencies, report and meters."""
    return (
        f"{result.passed} / {result.total} cases passed; "
        f"p50 {_format_ms(result.p50_ms)} ms; p95 {_format_ms(result.p95_ms)} ms; "
        f"report {_display_path(result.report_path)}; "
        f"meters {_display_path(result.meter_path)}"
    )


def _env_port() -> int | None:
    """Read DISPUTE_PORT, or None when unset; a value that is not an int is an error."""
    raw = os.environ.get("DISPUTE_PORT")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError as error:
        raise LoopError(
            f"DISPUTE_PORT must be a whole number, not {raw!r}"
        ) from error


def _env_path(name: str) -> Path | None:
    """Read one path from the environment, or None when it is unset."""
    raw = os.environ.get(name)
    return None if raw is None else Path(raw)


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, run the loop and print one summary line.

    A flag wins over its DISPUTE_ environment variable, and that variable wins over
    the default. A DISPUTE_PORT that is not a whole number is an error.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help="Dataset directory (fallback: DISPUTE_DATA, then data/dev).",
    )
    parser.add_argument(
        "--gold",
        type=Path,
        default=ROOT / "feedback" / "dev_gold.json",
        help="Development answers.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Mock port (fallback: DISPUTE_PORT, then a free port).",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=None,
        help="Mock state file (fallback: DISPUTE_STATE, then .state/loop-<port>.sqlite).",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "reports" / "scored-run.json",
        help="Where the run writes its JSON report.",
    )
    parser.add_argument(
        "--case-meters",
        type=Path,
        default=ROOT / "reports" / "meters.jsonl",
        help="Where the run writes one meter line per case.",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=ROOT / "reports" / "scored-run.md",
        help="Where the run writes its readable report.",
    )
    parser.add_argument(
        "--submission",
        type=Path,
        default=ROOT / "submissions" / "scored-run.json",
        help="Where the run writes the evaluator array.",
    )
    parser.add_argument(
        "--health-timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for GET /health.",
    )
    args = parser.parse_args(argv)
    try:
        port = args.port if args.port is not None else _env_port()
        data = (
            args.data
            if args.data is not None
            else _env_path("DISPUTE_DATA") or ROOT / "data" / "dev"
        )
        state = (
            args.state if args.state is not None else _env_path("DISPUTE_STATE")
        )
        result = run_loop(
            data_dir=data,
            gold=args.gold,
            port=port,
            state_path=state,
            report_path=args.report,
            meter_path=args.case_meters,
            markdown_path=args.markdown,
            submission_path=args.submission,
            health_timeout=args.health_timeout,
        )
    except LoopError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(_summary_line(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
