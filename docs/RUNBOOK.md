# Runbook: the demo loop

This is the operator and developer runbook for the loop. It covers the one command, the step-by-step path, the ports and state files, the environment variables and the failures we have actually hit.

Last verified: 2026-10-28 at 8553bb3, mock on port 8855. The published numbers are in `reports/scored-run.md`.

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
- No network and no credentials for the mock and the published scored run. The drafting commands use the hybrid model by default; when it cannot be set up they fall back to the rules. The published scored run stays offline.

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

A successful run looks like this. It is a real run from this tree, pointed at a scratch directory so it did not republish the committed report:

```sh
uv run --locked python -m src.run_loop --report .loop-check/scored-run.json \
    --case-meters .loop-check/meters.jsonl --markdown .loop-check/scored-run.md \
    --submission .loop-check/submission.json
```

```text
Fictional training mock at http://127.0.0.1:61678; Ctrl-C stops it.
12 / 12 cases passed; 0 format errors; p50 33.000 ms; p95 3916.000 ms; cost per case 0.00 USD
12 / 12 cases passed; p50 33.000 ms; p95 3916.000 ms; report .loop-check/scored-run.json; meters .loop-check/meters.jsonl
```

- 12 of 12 is the expected result at this commit: CARD-D09 builds because COF-43 reads the statement from the customer's text before the form fields.
- p50 and p95 move between runs because the retries wait on the wall clock: the committed report holds 31.000 and 3670.000 ms, this run 33.000 and 3916.000 ms.
- The last line names both the report and the meter file. With the defaults it ends `report reports/scored-run.json; meters reports/meters.jsonl`.
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
uv run --locked python -m src.review_runner submit --base-url http://127.0.0.1:8765 --data data/dev
```

The first command prints one contract per built case and names on stderr each case it could not build. The second drafts and scores every case and publishes the report. `make score` wraps the second command. The third opens one human review per built draft and keeps them in `reports/reviews.json`, which `check` reads later; add `--case CARD-D01` to open a single review. Without it, `pending` below lists nothing and `check` has no journal to read.

Each command reads the bank again. CARD-D10's one injected failure is spent by the first read after a reset, so show its retry from the first command's output, not from a later one.

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

The agent must not run the approval command in the live demo. The mock's CLI simulates a human boundary; during assessment the assessor controls approval and state. In rehearsal a driver may run it only as a stand-in, and the record must name that.

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
| `MODEL_PROVIDER` | drafting commands, `tools/run_model.sh` | `azure_openai` in drafting; unset means off in `model_from_env` | `off` disables the hybrid; `replay` needs `MODEL_REPLAY` |
| `MODEL_ID` | drafting commands, `tools/run_model.sh` | `gpt-6-luna` | Deployment or model name; it must match a passed entry in `models.toml` |
| `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` | Azure OpenAI | unset | The live pair's endpoint and key |
| `ANTHROPIC_FOUNDRY_RESOURCE` and `ANTHROPIC_FOUNDRY_API_KEY` | Claude on Foundry | unset | Used when `MODEL_PROVIDER=anthropic_foundry` |
| `MODEL_REPLAY` | replay | unset | Recording read when `MODEL_PROVIDER=replay` |

`.env.example` documents `PYTHONUTF8`, `DISPUTE_PORT`, `DISPUTE_DATA`, `DISPUTE_STATE` and the model names. The loop reads the three `DISPUTE_*` names as fallbacks when `--port`, `--data` and `--state` are omitted, and a flag always wins. Nothing in the example is a secret; a filled `.env` may hold the model key, and git ignores it. If you copy it, export it by hand in Git Bash and run the loop:

```sh
set -a; . ./.env; set +a
uv run --locked python -m src.run_loop
```

`make serve` and `make score` take `PORT` and `STATE` explicitly, so pass the values: `PORT=$DISPUTE_PORT STATE=$DISPUTE_STATE make serve`.

### Live model run

The drafting commands use the hybrid by default; `tools/scored_run.py` stays rules-only. Put the provider values in `.env` (gitignored) or in the environment:

```sh
MODEL_PROVIDER=azure_openai
MODEL_ID=gpt-6-luna
AZURE_OPENAI_ENDPOINT=https://RESOURCE.openai.azure.com
AZURE_OPENAI_API_KEY=...
```

The portal sometimes shows the endpoint with an operation path, such as
`https://RESOURCE.services.ai.azure.com/openai/v1/responses`. Paste that value or
the resource URL; the client strips the operation path and builds one base URL.

`tools/run_model.sh` sources `.env`, checks the pair, and writes `reports/scored-run-hybrid.json` and `reports/scored-run-hybrid.md`:

```sh
bash tools/run_model.sh
```

`SUITES="dev synth stress holdout" bash tools/run_model.sh` covers every suite. To test the wiring without a key, replay the recording:

```sh
MODEL_PROVIDER=replay MODEL_REPLAY=evals/recordings/gpt-6-luna.jsonl bash tools/run_model.sh
```

`MODEL_PROVIDER=off` disables the hybrid. Keep the key in `.env` or the environment, never in `models.toml`.

## Severity-1 incident path

Three failures stop the demo. For each: detect, stop, preserve, notify, restore. The state file is `.state/mock.sqlite`; its tables are `reviews`, `records`, `keys`, `calls` and `audit`. The audit is append-only by convention, not by hash chain. Never run `reset --confirm` during an incident: it deletes all five tables, including the audit.

### Suspected restricted-value leak

- Detect: `grep -n 'SYNTHETIC-PRIVATE-CARD-' reports/meters.jsonl reports/scored-run.json`. A case whose meter line was refused has no line in `reports/meters.jsonl` and `"meter_error": "MeterLeak"` in `reports/scored-run.json`; `src/meters.py:108-121` raises `MeterLeak` and `src/contract_records.py:219-220` catches it; after the run, `tools/scored_run.py:758-774` checks the written file and refuses the run with "found a restricted value. The run is refused and no report was written" if one is still there.
- Stop: stop the scored run and the mock. Do not open the meter file in a browser or paste it into chat.
- Preserve: copy `.state/mock.sqlite`, `reports/meters.jsonl`, `reports/scored-run.json` and `reports/scored-run.md` to `.state/incident-<utc>/`; record the case id and the refusal text.
- Notify: Ken (Lead) and the security owner. Name the file and the case, not the value.
- Restore: fix the redaction in `src/untrusted.py` or the leaking field, regenerate from a clean tree, then confirm `grep` finds no token and `wc -l reports/meters.jsonl` is 12.

### Unapproved or post-approval-modified write

- Detect: `uv run --locked python tools/runtime.py audit --state .state/mock.sqlite` shows `unapproved_write_attempt`; `POST /v1/records` returns 403 `approval_missing_or_draft_changed`; `src/review_gate.py:93-94` compares the draft hash and raises `ReviewRefused(403, "changed")`; `tools/runtime.py:154-155` audits the refusal.
- Stop: stop the beat. Do not retry with a new idempotency key; that hides the mismatch.
- Preserve: copy the state file, then save the review id and draft hash, the HTTP status and body, and the audit JSON. `GET /v1/reviews/<id>` shows the stored hash; `GET /v1/records/<case_id>` shows an existing record.
- Notify: Ken and the operator who approved the draft. The approval is invalid for this draft.
- Restore: reset only after preserving, submit the draft again, approve the exact hash, and confirm one `record_created`. Never edit the database to force an approval.

### Audit-trail loss or corruption

- Detect: the audit command fails, `PRAGMA integrity_check` is not `ok`, `seq` has gaps, or a record exists with no `record_created`. Run:
    uv run --locked python tools/runtime.py audit --state .state/mock.sqlite > .state/incident/audit.json
    uv run --locked python -c "import sqlite3; db=sqlite3.connect('.state/mock.sqlite'); print(db.execute('PRAGMA integrity_check').fetchone()[0])"
- Stop: stop the demo. Do not reset and do not run another beat on this state.
- Preserve: copy the whole `.state/mock.sqlite`, plus any `-wal` and `-shm` files, and keep the audit JSON and report files.
- Notify: Ken. State that the audit table is not tamper-evident and has no hash chain.
- Restore: restore a known-good state copy, or rebuild and disclose the lost interval. Do not claim the lost rows.

## Troubleshooting

| Symptom | Why | Fix |
|---|---|---|
| The loop fails with `the mock at http://127.0.0.1:8765 did not answer GET /health within 30.0 seconds; start it by hand to see its error`, or a run talks to an unexpected mock | A stale listener holds the port | `netstat -ano | grep :8765`, then `taskkill /F /PID <pid>`. Or let the loop pick a free port, or run `PORT=8794 make serve` / `--port 8794` |
| Old reviews and records appear in a fresh demo | A stale `.state/mock.sqlite` | Stop the mock, `uv run --locked python tools/runtime.py reset --confirm`, start again. `make clean` removes `.state`. The loop always uses `.state/loop-<port>.sqlite` |
| PowerShell redirect produces JSON the loader cannot read | PowerShell 5.1 writes UTF-16 with a BOM on `>`; the loader expects UTF-8 | Use Git Bash or cmd, or `| Out-File -Encoding ascii submissions/results.json`. Check with `od -An -tx1 -N3 submissions/results.json`: `3C` is bytes 3C 7B, FF FE is UTF-16 |
| `uv sync --locked` refuses, or uv does not know Python 3.12.13 | The installed uv predates the pin, or the interpreter is missing | `uv --version`, `uv self update` (or `brew upgrade uv`), then `uv sync --locked`. Never edit the pin in `pyproject.toml` |
| `git status` shows `reports/meters.jsonl` changed after a pytest run | Tests ran from the wrong directory, or a test used the scored run's default paths instead of a temp directory | Run pytest from the repository root. Tests must pass explicit report and meter paths, as `tests/test_scored_run.py` does. Restore the file with `git checkout -- reports/meters.jsonl` and confirm with `git status` |
| A case is refused with `the intake statement is not an exact excerpt of the intake` | The intake statement wraps across lines, so no single line is one exact excerpt. CARD-D09 no longer hits this, because COF-43 reads the customer's text before the form fields | No code fix. If another case hits it, do not edit the fixture; `docs/RED_TEAM.md:52` explains the limit |
| `make` is not installed on Windows | make is optional | Run the `uv run --locked` command the recipe wraps; every target is one command |

## Demo stop points

The full list is in `docs/DEMO_REHEARSAL.md`. Stop or use the recorded fallback when any of these is true:

- `/health` is not 200, or `/v1/cases` does not list twelve cases.
- The scored run is not 12 of 12, or has a format error.
- The report commit is not the build being demonstrated, or `git_dirty` is true.
- `pending` shows a review you did not create, or a record already exists for the case being demonstrated.
- A draft's decision fields differ from the numbers lock, or a second `record_created` or any forbidden write appears.
- A live change does not alter the draft, or breaks a test outside its own module.
- p95 is above 2500 ms: quote the report value and the sheet's 2.5 s line, and say it is a known gap.

## Where to look next

- `README.md` for the assessment-facing description and the measured numbers.
- `docs/DEMO_REHEARSAL.md` for the six demo beats and the numbers lock.
- `docs/FALLBACK.md` for the 6 to 8 minute fallback, the missing recording, and the artifact list.
- `docs/rehearsal-transcript-2026-10-28.txt` for exact CARD-D09 refusal and live-change output.
- `docs/RED_TEAM.md` for the known gaps, including the intake statement that wraps across lines at line 52.
- `docs/decisions/ADR-004-one-entry-point-for-the-loop.md` for why the loop is one tested command.
- `reports/scored-run.md` for the per-case results of the published run.
