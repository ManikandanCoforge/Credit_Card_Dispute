# Deck evidence pack: Lumen Bank dispute copilot

Prepared 2026-10-28 for the Thursday 29 October 2026 demo and defence.
Every row was produced against **origin/main at `8553bb36a05ba3b0b6c96b5dffb82aa96c6d7283`**
("Merge pull request #87 from ManikandanCoforge/kenmann01/cof-34-refresh-requirements-trace",
2026-10-27 23:03 ET), read in the worktree `.worktrees/lane-deck`. The published
scored run was made at `8c3ac7f4859c0ec9c36a51ef26e78451a46c2889` and records
`git_dirty false`; `8c3ac7f..8553bb3` touches only README, docs, reports and
tests, so the run describes main's code. No number here is estimated.

Environment: `D:/20-projects/credit-card-dispute/.venv/Scripts/python.exe`
(Python 3.12, pytest, pytest-cov 7.1.0). The venv was used, not `uv`.

## How to reproduce

```bash
# one command: free port, own state, supplied mock, health wait, scored run
uv run --locked python -m src.run_loop

# the gate (pyproject.toml sets --cov-fail-under=100)
D:/20-projects/credit-card-dispute/.venv/Scripts/python.exe -m pytest -q
D:/20-projects/credit-card-dispute/.venv/Scripts/python.exe -m mypy src tools evals
D:/20-projects/credit-card-dispute/.venv/Scripts/python.exe -m ruff check src tools evals
D:/20-projects/credit-card-dispute/.venv/Scripts/python.exe -m bandit -c pyproject.toml -r src tools evals
```

The committed artifact is `reports/scored-run.json` plus `reports/scored-run.md`
and `reports/meters.jsonl`. A mock left running on a port serves the next run
with its own fault counters, so the loop gives each run a fresh state file at
`.state/loop-<port>.sqlite`.

## Claim table

| Claim | Value | Provenance |
| --- | --- | --- |
| Main commit | `8553bb3`, "Merge pull request #87 ...", 2026-10-27T23:03 ET | `git show -s --format='%H %cI %s' origin/main` |
| CI on main | Workflow "checks" succeeded; jobs lint, bandit, pytest, env-files, pytest-windows | `.github/workflows/checks.yml`; GitHub checks |
| Test suite on main | **1014 passed**, 0 failed, 0 skipped | `python -m pytest -q`, 126.39 s, run 2026-10-28 in this worktree |
| Line coverage | **100.00% over 3404 statements**, 0 missed | same pytest run; gate `--cov-fail-under=100` |
| mypy | "Success: no issues found in 44 source files" | `-m mypy src tools evals` |
| ruff, bandit | "All checks passed!"; "No issues identified." (7252 LOC, 17 nosec) | `-m ruff check src tools evals`; `-m bandit -c pyproject.toml -r src tools evals` |
| Scored dev cases | **12 / 12 pass**, 0 format errors, **no exceptions**, no unplanned failures | `reports/scored-run.json` and `.md`, `git_commit 8c3ac7f`, `git_dirty false`, generated 2026-10-28T02:10:46Z |
| p50, p95 draft latency | **31.000 ms**, **3670.000 ms** | `reports/scored-run.md` |
| Meter rows | 12 rows, one per case; 27 tool attempts, 3 retries in total | `reports/meters.jsonl` |
| Model calls, tokens, cost | 0 calls, 0 tokens, 0.00 USD total and per case | all 12 meter rows; the deterministic template makes no call, so 0.00 USD is by construction |
| Base URL at run time | `http://127.0.0.1:8834`; dataset `card-disputes-dev` | `reports/scored-run.json` |
| D07 | 3670.626 ms, 4 attempts, 2 retries | meter row; D07 fault injection `{'transactions': {'failures': 2}}` |
| D10 | 1290.001 ms, 3 attempts, 1 retry | meter row; D10 fault injection `{'transactions': {'failures': 1}}` |
| Every other case | 2 attempts, 0 retries | meter rows |
| Per-case verdicts | see the table below; all twelve build | a fresh mock with a fresh state on port 8794, 2026-10-28, plus the published run |
| D01 draft hash | `af65f68659d94274382d90d07417c94031d0c574722bd7b8850e7700ce13ebd4` | reproduced from a fresh mock 2026-10-28; same hash in rehearsal runs 3 and 4 (`docs/DEMO_REHEARSAL.md`) |
| D01 audit walk | 5 rows: 2 `tool_read`, `review_requested`, `human_approved`, `record_created` | rehearsal runs 3 and 4 |
| Changed draft | refused before any write: `src/review_gate.py` raises a local 403 "changed" and posts nothing | `src/review_gate.py:93-94`, `tests/test_review_gate.py`. Never staged with a POST: the mock audits a changed-draft POST as `unapproved_write_attempt` |
| 409 on duplicate case | `409 {"error":"duplicate_case","existing_record_id":"dispute-double-02"}` | rehearsal runs 3 and 4, CARD-D09's approved redelivery of CARD-D02; code in `src/review_gate.py` |
| Review runner | `python -m src.review_runner submit` and `check` open the reviews and record approved drafts; a person approves with `tools/runtime.py approve` | the agent must never approve its own draft |
| Retry wiring | `ToolRetry` in `src/contract_records.py:170,254` and `src/review_runner.py:77`; real in the scored run (D07 4/2, D10 3/1) | source and meter rows |
| Model boundary | ADR-001, accepted 2026-10-25: a model may write prose only; class, route, facts, citations, deadline stay in code | `docs/decisions/ADR-001-model-narrative-boundary.md` |
| Model route status | ADR-003 merged (`186c8e9`), **off by default**, no approved live run, cost and latency at volume not measured | `docs/decisions/ADR-003-hybrid-model-questions.md`; published run has 0 calls |
| Pull requests | **0 open**; #52 merged `32d7820`, #63 merged `ef47e16`, #65 merged `186c8e9`, #66 closed (meters delivered as COF-43) | `gh pr list --state open` |

## Per-case verdicts (published run and fresh read, 2026-10-28)

| Case | Class | Route | Deadline | Citations |
| --- | --- | --- | --- | --- |
| D01 | unauthorized | ready_for_review | 2026-10-31 | 6 |
| D02 | duplicate_charge | ready_for_review | 2026-11-16 | 7 |
| D03 | service_not_received | ready_for_review | 2026-12-02 | 6 |
| D04 | unauthorized | request_information | 2026-10-31 | 6 |
| D05 | ambiguous | manual_review | null | 9 |
| D06 | unsupported | manual_review | null | 8 |
| D07 | unauthorized | manual_review | 2026-10-31 | 7 |
| D08 | duplicate_charge | ready_for_review | 2026-11-16 | 7 |
| D09 | duplicate_charge | ready_for_review | 2026-11-16 | 7 |
| D10 | service_not_received | ready_for_review | 2026-12-02 | 6 |
| D11 | unauthorized | ready_for_review | 2026-09-20 | 6 |
| D12 | service_not_received | request_information | 2026-12-03 | 6 |

- D05 cites both contradictory sources; D05 and D06 route to manual review because
  the evidence does not decide the answer. That is a decided outcome, not a failure.
- D07 has no amount or currency and still classifies and routes to manual review.
- D08's instruction-shaped merchant note is stored as data and is not cited.
- D09 is the duplicate of D02: transaction TX-D02, 134 XCR, deadline 2026-11-16.
- D11 reads the older CARD-POLICY-V1; the other eleven read CARD-POLICY-V2.
- D02, D03, D05 and D11 reset the deadline clock: 2026-11-16, 2026-12-02,
  null and 2026-09-20 respectively, counted from the reported date.

## Safe sentences (each carries its number)

1. On main at `8553bb3`, 1014 tests pass in about 126 s with 100.00% line
   coverage over 3404 statements, and CI fails if coverage drops below 100%.
2. The scored harness passes 12 of 12 dev cases with 0 format errors and no
   exceptions; p50 is 31.000 ms and p95 is 3670.000 ms.
3. One full pass makes 27 tool attempts with 3 retries: D07 needs 4 attempts and
   2 retries at 3670.626 ms, D10 needs 3 attempts and 1 retry at 1290.001 ms.
4. Every meter row records 0 model calls, 0 tokens and 0.00 USD; the shipped path
   is the deterministic template.
5. A record can only be created from the exact approved draft: the runner refuses
   a changed draft before it sends anything, and a second record for the same
   dispute returns 409 `duplicate_case`, verified in rehearsal with CARD-D09.
6. Approval binds to a sha256 of the canonical draft: the clean D01 walk produced
   `af65f68659d94274382d90d07417c94031d0c574722bd7b8850e7700ce13ebd4` and
   exactly 5 audit rows.
7. The model route is merged and off by default; no live model run is approved,
   and cost and latency at volume are not measured.
8. Zero pull requests are open. #52, #63 and #65 are merged; #66 was closed and
   its meters landed through COF-43.

## Do not claim

- **"7 of 12"**: that is the run before #52, #63 and #65 landed. Today it is 12 of 12.
- **"254 tests" or "718 statements"**: that was `df3daa4`. Today 1014 tests and
  3404 statements.
- **"20 tool reads" or "7.65 ms p95"**: the wire now retries. One pass makes 27
  attempts and 3 retries; p95 is 3670.000 ms, dominated by D07 and D10.
- **"25 audit rows for one hand-walked case"**: the measured D01 walk writes 5.
- **"#52, #63, #65 or #66 are in review"**: all four are closed. Zero are open.
- **"The retry ladder has no caller"**: `ToolRetry` is wired and the scored run
  exercises it. Waits are 1 s then 2 s, not 1/2/4 s.
- **"ADR-003 is accepted" or "a model answers two questions today"**: merged and
  off by default, with no approved live run.
- **"p95 latency is 9.559 ms"**: that is an older artifact; the published run is
  3670.000 ms.

## Gaps that remain

- Reviewer identity and authentication (M1).
- The live model route (M3): built, off, no approved run.
- Update and close actions, blocked by Gate U (L1).
- UI and production deployment (L2/L4).
- Wrapped customer statement line limit (`docs/RED_TEAM.md:52`).
- Ruleset enforcement, blocked by the GitHub plan (403).
