# Runbook: the demo loop

This is the operator and developer runbook for the loop. It covers the one command, the step-by-step path, the ports and state files, the environment variables and the failures we have actually hit.

## What the loop is

Four actors take part.

| Actor | What it is | Who starts it |
|---|---|---|
| Supplied mock | `tools/runtime.py serve`. Serves the dataset, the review queue and the record endpoint from one state file. Standard library only. | The loop, or you in a terminal |
| Copilot | The drafting and scoring code. `src.contract_records` drafts a case; `tools/scored_run.py` drafts and scores every case in process. | The loop, or you in a terminal |
| Operator gate | `tools/runtime.py pending`, `approve`, `reject` and `audit`. A person decides on the exact draft. | A person in a terminal, never the agent |
| Scored run | `tools/scored_run.py`. Drafts every case, scores it against the development answers, writes the report and the meter lines. | The loop, or you |

The loop is the only actor that owns a port, a state file and the output paths from beginning to end.

## Prerequisites

- `uv` that knows Python 3.12.13. uv 0.9.1 does not; CI uses 0.12.20. Run `uv self update` (or `brew upgrade uv`) if `uv sync --locked` stops on the pin.
- Git Bash or a POSIX shell for the Makefile recipes. `make` itself is optional; every recipe is one `uv run --locked` line.
- Windows: `PYTHONUTF8=1` before any command, or a non-ASCII merchant name is read in the locale encoding.
- Run every command from the repository root. `uv run --locked` uses `uv.lock` and the package paths are relative to the root.
- No network and no credentials. The mock binds loopback, and the default application makes no model call.

## The one-command path

With make:

```sh
make demo
```

Without make, the same command:

```sh
uv run --locked python -m src.run_loop
```

The loop makes the output directories, picks a free loopback port, starts the supplied mock on `.state/loop-<port>.sqlite`, waits up to 30 seconds for `GET /health`, runs the scored run into the report and submission paths, prints one summary line and stops the mock.

A successful run looks like this. It is a real run from this tree; it wrote into a scratch directory so it did not republish the committed report:

```text
Fictional training mock at http://127.0.0.1:8794; Ctrl-C stops it.
11 / 12 cases passed; 0 format errors; p50 31.000 ms; p95 4128.000 ms; cost per case 0.00 USD
  CARD-D09: submitted (the intake statement is not an exact excerpt of the intake)
11 / 12 cases passed; p50 31.000 ms; p95 4128.000 ms; report .loop-check/scored-run.json
```

- 11 of 12 is the expected result at this commit. CARD-D09 is the proposed COF-43 exception; see the troubleshooting table.
- p95 moves between runs (the committed report holds 3444.000 ms, this run 4128.000 ms) because the retries wait on the wall clock. p50 stays at 31 ms.
- With the defaults the last line ends `report reports/scored-run.json`.
- The first line comes from the supplied mock, the next two from the scored run, and the last from the loop.

Exit status: 0 when the run completed, including a run with a failing case, because a case failure is data. 1 when the mock did not answer `GET /health` within the timeout or the scored run wrote no readable report. In both failure cases the mock is stopped before the error propagates.

What the run writes, with the defaults:

| Path | Content |
|---|---|
| `submissions/scored-run.json` | the drafted array for the scored run |
| `reports/scored-run.json` | the report: pass count, per-case checks, percentiles, commit |
| `reports/scored-run-meters.json` | the meter rows for the run |
| `reports/scored-run.md` | the human-readable report |
| `reports/meters.jsonl` | one redacted meter line per case |
| `.state/loop-<port>.sqlite` | the mock state for this run |

These are the same committed files the manual scored run wrote, so the loop replaces the published numbers when it runs with the defaults. Commit them only when you mean to publish a new run, and check `git status` after a run you did not mean to publish.

Options: `--port`, `--state`, `--health-timeout`, `--data`, `--gold`, `--report`, `--case-meters`, `--markdown` and `--submission`. Run `python -m src.run_loop --help` for the defaults.

## The step-by-step path

The assessment expects the mock, the copilot and the operator to be separate, so this path runs them in three terminals. Use it for the demo when you want to show each step.

Terminal 1, the mock:

```sh
uv run --locked python tools/runtime.py reset --confirm
uv run --locked python tools/runtime.py serve --port 8765
```

Wait for `Fictional training mock at http://127.0.0.1:8765; Ctrl-C stops it.` `reset --confirm` starts from a clean state; skip it to keep the existing one. `make serve` wraps the second command, and `PORT=8794 make serve` uses another port.

Terminal 2, the copilot:

```sh
mkdir -p submissions
uv run --locked python -m src.contract_records http://127.0.0.1:8765 data/dev > submissions/results.json
uv run --locked python tools/scored_run.py --base-url http://127.0.0.1:8765
```

The first command prints one contract per built case and names on stderr each case it could not build. The second drafts and scores every case and publishes the report. `make score` wraps the second command.

Terminal 3, the operator. This is a person, not the agent:

```sh
uv run --locked python tools/runtime.py pending
uv run --locked python tools/runtime.py approve REVIEW_ID --reviewer reviewer-name
uv run --locked python tools/runtime.py audit > reports/audit.json
```

Then, back in terminal 2, record the approved drafts:

```sh
uv run --locked python -m src.review_runner check --wait 120
```

The agent must never run the approval command. The mock's CLI simulates a human boundary; during assessment the assessor controls approval and state.

The acceptance eval suite runs separately from the loop:

```sh
uv run --locked python -m evals --suite evals/suites/dev.json
```

or `make eval` where make is installed. The six demo beats and the numbers lock stay in `docs/DEMO_REHEARSAL.md`; this runbook does not replace them.

## Ports and state files

- 8765 is the documented default for the mock, in `serve`, `scored_run.py` and `make serve`.
- The loop picks a free loopback port when `--port` is not given, so it never collides with a listener left behind. It prints the base URL it chose.
- State: `.state/mock.sqlite` is the `serve` default; `.state/loop-<port>.sqlite` is the loop's own. `--state` overrides either. Two loops never share a state file.
- To reset a mock, stop it, run `uv run --locked python tools/runtime.py reset --confirm`, and start it again.
- `make clean` removes `.state`, `submissions` and the pytest temp directory `pytest-of-mannk`. It lists those paths explicitly and never removes the checkout.
- Check a suspect port with `netstat -ano | grep :8765`, then stop the process with `taskkill /F /PID <pid>`.

## Environment variables

| Name | Used by | Default | Why it matters |
|---|---|---|---|
| `PYTHONUTF8` | Python on Windows | unset | Set to `1` so the evaluator and the meter reader use UTF-8. In PowerShell: `$env:PYTHONUTF8 = "1"` |
| `PORT` | Makefile | `8765` | Port for `make serve`; `PORT=8794 make serve` |
| `STATE` | Makefile | `.state/mock.sqlite` | State file for `make serve` |
| `BASE_URL` | Makefile | `http://127.0.0.1:$(PORT)` | Base URL for `make score` |
| `DISPUTE_PORT` | `python -m src.run_loop` | unset | Port when `--port` is omitted; a value that is not a whole number fails the run |
| `DISPUTE_DATA` | `python -m src.run_loop` | `data/dev` | Dataset when `--data` is omitted |
| `DISPUTE_STATE` | `python -m src.run_loop` | `.state/loop-<port>.sqlite` | State file when `--state` is omitted |

`.env.example` documents `PYTHONUTF8`, `DISPUTE_PORT`, `DISPUTE_DATA` and `DISPUTE_STATE`. The loop reads the three `DISPUTE_*` names as fallbacks when `--port`, `--data` and `--state` are omitted, and a flag always wins. Nothing in the file is a secret, and `.env` itself is ignored. If you copy it, export it by hand in Git Bash and run the loop:

```sh
set -a; . ./.env; set +a
uv run --locked python -m src.run_loop
```

`make serve` and `make score` take `PORT` and `STATE` explicitly, so pass the values: `PORT=$DISPUTE_PORT STATE=$DISPUTE_STATE make serve`.

The optional hybrid model reads `MODEL_PROVIDER` and the related names; see the README section. The default run needs none of them.

## Troubleshooting

| Symptom | Why | Fix |
|---|---|---|
| The loop fails with `the mock at http://127.0.0.1:8765 did not answer GET /health within 30.0 seconds; start it by hand to see its error`, or a run talks to an unexpected mock | A stale listener holds the port | `netstat -ano | grep :8765`, then `taskkill /F /PID <pid>`. Or let the loop pick a free port, or run `PORT=8794 make serve` / `--port 8794` |
| Old reviews and records appear in a fresh demo | A stale `.state/mock.sqlite` | Stop the mock, `uv run --locked python tools/runtime.py reset --confirm`, start again. `make clean` removes `.state`. The loop always uses `.state/loop-<port>.sqlite` |
| PowerShell redirect produces JSON the loader cannot read | PowerShell 5.1 writes UTF-16 with a BOM on `>`; the loader expects UTF-8 | Use Git Bash or cmd, or `| Out-File -Encoding ascii submissions/results.json`. Check with `od -An -tx1 -N3 submissions/results.json`: `3C` is bytes 3C 7B, FF FE is UTF-16 |
| `uv sync --locked` refuses, or uv does not know Python 3.12.13 | The installed uv predates the pin, or the interpreter is missing | `uv --version`, `uv self update` (or `brew upgrade uv`), then `uv sync --locked`. Never edit the pin in `pyproject.toml` |
| `git status` shows `reports/meters.jsonl` changed after a pytest run | Tests ran from the wrong directory, or a test used the scored run's default paths instead of a temp directory | Run pytest from the repository root. Tests must pass explicit report and meter paths, as `tests/test_scored_run.py` does. Restore the file with `git checkout -- reports/meters.jsonl` and confirm with `git status` |
| CARD-D09 is refused with `the intake statement is not an exact excerpt of the intake` | The intake statement is split across two lines, so it is not one exact excerpt. This is the proposed COF-43 exception | None. It is the known gap, and `docs/RED_TEAM.md:52` explains it. Do not present it as passing and do not edit the fixture |
| `make` is not installed on Windows | make is optional | Run the `uv run --locked` command the recipe wraps; every target is one command |

## Where to look next

- `README.md` for the assessment-facing description and the measured numbers.
- `docs/DEMO_REHEARSAL.md` for the six demo beats and the numbers lock.
- `docs/RED_TEAM.md` for the known gaps, including CARD-D09 at line 52.
- `docs/decisions/ADR-004-one-entry-point-for-the-loop.md` for why the loop is one tested command.
- `reports/scored-run.md` for the per-case results of the published run.
