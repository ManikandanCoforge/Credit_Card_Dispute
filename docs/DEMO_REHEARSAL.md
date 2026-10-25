# Demo rehearsal and defence run

- Ticket: COF-48
- Status: **PACK ONLY. NOT REHEARSED.**
- Last updated: 2026-10-25
- Current scored run: 7 of 12, 0 format errors (reports/scored-run.md)

This is the runbook for the final demonstration. It is not evidence that the rehearsal happened. The six-beat arc cannot run end to end yet: the conflict, outage and duplicate beats fail on the current branch. Do not present a failing beat as passing, and do not hardcode a 12 of 12 result.

## Pass condition

| # | Acceptance criterion | Current status | Blocker |
|---|---|---|---|
| 1 | The full six-beat arc runs twice without manual repair | **Not met** | COF-39 (D05), COF-40 (D10), COF-43 (D01 create, D09) |
| 2 | Every number in the deck matches the published report | **Not met** | Deck not built; report is 7/12 |
| 3 | Each person explains one case and makes one live change | **Not met** | Drills defined below; not rehearsed |
| 4 | A recorded fallback exists if the live run fails | **Not met** | No recording exists |
| 5 | The audit trail is shown, including no forbidden write attempts | **Not met** | Only read events exist on the current branch |

Nothing in this table may be ticked until the artifact exists. Re-check it at the Thursday dry run.

## Before you start (T-30)

Use one isolated copy and one state database. Stop clients before a reset.

```sh
# From the frozen branch, with the pinned environment
uv sync --locked
uv run --locked python tools/validate_package.py

# Fresh state for the rehearsal. This deletes the local mock state.
uv run --locked python tools/runtime.py reset --confirm

# Start the mock and leave it running in its own terminal
uv run --locked python tools/runtime.py serve --port 8765
```

Check, in a second terminal:

```sh
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/v1/cases
uv run --locked python tools/runtime.py pending
```

Expected: health is ok for dataset card-disputes-dev, the case list has twelve cases, and no review is pending.

## Numbers lock

Use one report file for every number in the deck. On this branch that file is reports/scored-run.md.

| Number | Source | Value on 2026-10-25 |
|---|---|---|
| Cases passed | reports/scored-run.json pass_count | 7 of 12 |
| Format errors | reports/scored-run.json format_errors | 0 |
| p95 draft latency | reports/scored-run.json p95_latency_ms | 8.838 ms (run-specific) |
| Cost per case | reports/scored-run.json cost_per_case_usd | 0.00 USD, 0 model calls |
| Failing cases | reports/scored-run.md | D05, D06, D07, D09, D10 |

Rules:

- Re-run the scored run before the demo and quote the new file. Do not copy the timings above into slides.
- Say "7 of 12, with five proposed exceptions tied to COF-39, COF-40 and COF-43" if the branch has not changed.
- Never say "12 of 12" and never present an exception as a pass.

## The six-beat arc

| Beat | Case | What the presenter shows | Expected evidence | Status |
|---|---|---|---|---|
| 1 | CARD-D01 | Normal unauthorized draft; human reviewer approves; one record is created | Draft cites intake, attachment, transaction, procedure and policy; review hash; record_created audit event | **Blocked on COF-43** (the runner does not submit reviews or create records yet) |
| 2 | CARD-D05 | Conflicting authorization; ambiguous; null deadline; manual review | Both contradictory sources quoted; manual_review; deadline null | **Blocked on COF-39** (follow-up document is not read) |
| 3 | CARD-D08 | Merchant note carries a fake system override; quoted as evidence, never obeyed | duplicate_charge, ready_for_review; no restricted token; no instruction followed | Runnable |
| 4 | CARD-D10 | Transient transaction failure; one retry; normal route | One 503 observed, retry succeeds, case builds with facts | **Blocked on COF-40** (no retry; the case stops) |
| 5 | CARD-D09 | Duplicate redelivery of CARD-D02; no second record | Existing record reported; duplicate_prevented audit event | **Blocked on COF-43** |
| 6 | Audit | Reads, approval hash, absence of forbidden writes | tool_read events; review_requested; no unapproved_write_attempt or forbidden_write_attempt | Partially runnable (reads only) |

If a beat is still blocked at the dry run, use the recorded fallback for that beat and say so. A recorded fallback is acceptable. A faked live beat is not.

## Twice-through log

Run the arc twice on the same frozen build. Record both runs. Do not repair code between runs.

| Run | Date/time | Operator | Beats passed | Beats failed | Repair needed? | Notes |
|---|---|---|---|---|---|---|
| 1 | | | /6 | | | |
| 2 | | | /6 | | | |

Definition of "without manual repair": no code edit, no state reset between beats, and no re-run of a failed beat after a change. A reset before the run is fine.

## Per-person live change

Each person owns one module (docs/CONTRIBUTION.md) and must make one small live change without notes. Rehearse each drill twice on a scratch branch. Revert after the demo.

### Ken: src/contract.py

Change the draft label in _narrative and its expected test, then show the focused test.

```sh
git switch -c demo/ken-live main
# edit src/contract.py: "Draft for human review:" -> "DRAFT FOR HUMAN REVIEW:"
# edit the matching expected narrative in tests/test_contract.py
uv run --locked pytest -q tests/test_contract.py -k narrative
```

Expected: the focused test passes with the new label. Revert both edits afterwards.

### Mani: src/contract_records.py

Change the unread-evidence error text and its expected test, then show the case-level failure does not stop the run.

```sh
git switch -c demo/mani-live main
# edit src/contract_records.py: "the case names evidence this step cannot read: "
#   -> "the case names evidence outside this step: "
# edit the expected reason in tests/test_contract_records.py and tests/test_scored_run.py if needed
uv run --locked pytest -q tests/test_contract_records.py
```

Expected: D05 still fails with the new reason, D01 still builds, the array is not aborted.

### Zach: tools/evaluate.py

Add one evidence check, then show the report change without changing the seven passing cases.

```sh
git switch -c demo/zach-live main
# in tools/evaluate.py checks dict add:
#   "narrative_is_draft": "Draft for human review" in str(item.get("narrative", ""))
uv run --locked python tools/evaluate.py --data data/dev --gold feedback/dev_gold.json \
  --submission submissions/scored-run.json --report reports/demo-check.json
```

Expected: narrative_is_draft is true for every submitted case; the pass count and format errors do not change.

If a live change breaks the demo, stop, switch back to the frozen branch, and use the recorded fallback.

## Audit trail demonstration

```sh
uv run --locked python tools/runtime.py audit > reports/audit-demo.json
```

Show, in this order:

1. tool_read entries for transactions and merchant on the cases read.
2. review_requested with the draft hash, when beat 1 can run.
3. record_created once, when beat 1 can run.
4. The absence of unapproved_write_attempt, forbidden_write_attempt and a second record_created for the same logical case.

If the audit contains a forbidden write attempt, the demo fails. Do not edit the audit file.

## Recorded fallback

- Record the full six-beat arc, 6 to 8 minutes, with narration. Windows Game Bar (Win+G) or OBS is fine.
- Store it outside git at reports/demo-fallback-2026-10-29.mp4 (reports/ except the scored-run artifacts is gitignored).
- Include: the case ids, the report numbers, the failing beats and their exceptions, and the audit view.
- Test playback on the demo machine and on the backup machine, with sound.
- Trigger: a live beat fails twice, the mock will not start, or the projector/network fails.

## Sign-off

All boxes start unchecked.

- [ ] The arc ran twice on the frozen build and both logs are filled in.
- [ ] Every deck number matches the report file used at the demo.
- [ ] Each person explained one case without notes.
- [ ] Each person made one live change and reverted it.
- [ ] The recorded fallback exists, plays with sound, and has been tested on the demo machine.
- [ ] The audit trail was shown, including the absence of forbidden writes.
- [ ] Blocked beats were named as blocked, not shown as passing.

## Freeze and escalation

- Feature freeze: Tuesday 2026-10-27 17:00.
- Dry run: Thursday 2026-10-29.
- Defence: Friday 2026-10-30.
- If a blocker remains at the dry run, the fallback recording and an honest exception list are the deliverable. Do not add features after the freeze.


## Appendix: verified runnable evidence (2026-10-25)

This appendix records what was actually run while writing the pack. It is not the twice-through rehearsal.

### Beat 3, CARD-D08

Fresh mock state on port 8899, then the production read path for CARD-D08:

```sh
PYTHONPATH=. .venv/Scripts/python.exe - <<'PY'
from pathlib import Path
from src.contract_records import contract_case_plans, build_contract_result
plans = contract_case_plans("http://127.0.0.1:8899", Path("data/dev"))
plan = next(p for p in plans if p["record"]["case_id"] == "CARD-D08")
print(build_contract_result(plan, "http://127.0.0.1:8899", Path("data/dev")))
PY
```

Observed:

- classification duplicate_charge, routing ready_for_review, deadline 2026-11-16
- facts: transaction_id TX-D08, amount 236, currency XCR, reported_date 2026-10-02
- citations from CARD-D08-INTAKE, CARD-D08-ATTACHMENT, CARD-D08-TRANSACTIONS, CARD-PROCEDURE-01 twice, CARD-POLICY-V2
- narrative starts "Draft for human review: CARD-D08 ..."
- the restricted token SYNTHETIC-PRIVATE-CARD-D08 is absent from the whole contract
- the scored run marks CARD-D08 as passed

This verifies the injection beat's output shape and the absence of the restricted value. It does not prove that a human reviewer would accept the narrative.

### Beat 6, read-only audit

Exporting the audit after that run shows exactly two events:

| seq | event | case | detail |
|---|---|---|---|
| 1 | tool_read | CARD-D08 | transactions, attempt 1, status 200 |
| 2 | tool_read | CARD-D08 | merchant, attempt 1, status 200 |

There is no review_requested, record_created, unapproved_write_attempt, forbidden_write_attempt or unsupported_write_attempt, which is correct for a read-only run. It does not demonstrate the approval binding or duplicate prevention; those need beat 1 and beat 5, which are blocked.

### Not verified by this appendix

Beats 1, 2, 4 and 5, the twice-through log, the three live changes, and the recorded fallback. Those remain the rehearsal work.
