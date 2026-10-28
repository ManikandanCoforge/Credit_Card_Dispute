# ADR-004: One entry point for the loop

- Status: Accepted
- Date: 2026-10-27
- Ticket: COF-73 (#80)
- Owner: Ken (kenmann01)
- Related: `README.md`, `docs/RUNBOOK.md`, `Makefile`, `tests/test_docs_numbers.py`

## Context

The demo loop was eight commands over two terminals: start the mock, read `/health` and `/v1/cases`, draft every case, evaluate the array, run the scored run, then the operator approval and the record check. Each step was remembered by hand.

Four incidents came from the gap between those commands:

- a stale listener on 8765 answered a new run with an old mock
- a stale `.state/mock.sqlite` carried reviews and records into a fresh demo
- a test run from the wrong directory wrote `reports/meters.jsonl` into the checkout
- the README numbers drifted from `reports/scored-run.json`

None of these are logic failures. They are failures of ownership: no single place owned the port, the state file, the output paths, or the published numbers.

## Decision

`src/run_loop.py` is the one entry point. `python -m src.run_loop` makes the output directories, picks a free loopback port when none is given, starts the supplied mock on a state file of its own, waits for `GET /health`, runs `tools/scored_run.py` with explicit artifact paths, reads the report, prints one summary line and stops the mock in a `finally` block.

Two Protocol seams keep the failure paths testable:

- `ProcessRunner` starts an argv and returns a `RunningProcess` with `poll`, `terminate` and `wait`; `SubprocessRunner` is the real adapter over `subprocess.Popen`.
- `HealthProbe` waits on a base URL; `HttpHealthProbe` is the real adapter over `urllib.request` and `GET /health`.

Tests inject fakes and cover port selection, the default state path, a health timeout that stops the mock, child exit codes and a report that was not written. One integration test starts the real mock and runs the real scored run on a free port.

Exit codes separate the loop from the data. A completed run exits 0 even with a failing case; it exits 1 only when the mock never became ready or the scored run wrote no readable report. A case failure is data, not a loop error.

On the command line a flag wins over its `DISPUTE_` variable, and the variable wins over the default: `DISPUTE_PORT`, `DISPUTE_DATA` and `DISPUTE_STATE`. A `DISPUTE_PORT` that is not a whole number is a clear error, not a silent fallback.

The `Makefile` is thin sugar over the same commands: `setup`, `gate`, `serve`, `score`, `demo`, `eval` and `clean`. It carries no logic the Python entry point does not.

Docs drift is a test now: `tests/test_docs_numbers.py` compares the numbers in the README paragraph, the rehearsal numbers lock and `reports/scored-run.md` with `reports/scored-run.json`, and names the file, the number it found and the number the report holds.

## Rejected alternative

A bash script that starts the mock, runs the scored run and stops the mock again.

## Why the alternative was rejected

- No seam for the failure paths. A health timeout, a child exit code and the stop-on-failure path would only be exercised by hand, which is the problem the change exists to remove.
- The repository gate covers Python. A shell script sits outside pytest, mypy, ruff and bandit, so its coverage and behavior would not be checked.
- Two shells. It would need a POSIX and a PowerShell copy on this team's machines. The Makefile already carries the POSIX form, and the Python command is the same on both.

## Rejected alternative

A pytest fixture that starts the mock and runs the scored run.

## Why the alternative was rejected

- pytest is the gate, not the operator's tool. Binding the demo to the test runner makes a case failure look like a test failure and ties the operator's exit code to pytest's.
- The fixture would still need a port and a state file, which are the loop's job. Moving them into `conftest.py` hides the ownership rather than fixing it.

## Rejected alternative

docker compose, with the mock in one service and the run in another.

## Why the alternative was rejected

- It hides the port problem behind a container network instead of giving the operator a free port and a printed base URL.
- It adds a dependency the assessment machine may not have. The mock is standard library and binds loopback.
- It leaves the state file and the published numbers where they were.

## Consequences

- `src/run_loop.py` is new code under the 100 percent coverage gate: the adapters, the CLI, the error paths and the report reader are covered by tests.
- The loop owns the port, the state file and the output paths. Two loops never share a state file: the default is `.state/loop-<port>.sqlite`.
- The operator approval stays outside the loop. The agent must never run `tools/runtime.py approve`, and the loop never calls the approval or record endpoints.
- Reports and submissions are still written only when a run publishes. The loop replaces the committed `reports/scored-run.*` when it runs with the defaults, so commit those files only when publishing.
- The docs numbers are machine-checked. A stale number fails the gate and names the file, the number it found and the number the report holds.
- `make` is optional. Where make is absent, the `uv run` command is the same, and the runbook shows both forms.

## Review triggers

- The mock's readiness contract changes from `GET /health`.
- A second consumer needs the report reader or the free-port helper.
- make becomes mandatory for an assessment machine, and the Windows and Git Bash requirements need documenting there.
- The loop grows beyond one mock and one scored run.
