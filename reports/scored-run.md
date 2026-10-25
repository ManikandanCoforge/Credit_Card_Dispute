# Scored run across the twelve dev cases

Generated at 2026-10-25T21:00:06Z from commit `760447fc74c640fcda053c49fbc4b9b3f61a7251` against `http://127.0.0.1:8899`. The working tree had uncommitted changes when the report was generated.
Dataset: `card-disputes-dev`.

## Result

- Pass: 7 / 12
- Format errors: 0
- p95 draft latency: 8.838 ms (nearest-rank over the measured durations)
- Cost per case: 0.00 USD (0 model calls and 0 tokens in the meter file)
- Total cost: 0.00 USD

## Case results

| Case | Submitted | Passed | Duration (ms) | Failed checks | Error |
|---|---|---|---|---|---|
| CARD-D01 | yes | yes | 8.838 | - | - |
| CARD-D02 | yes | yes | 6.818 | - | - |
| CARD-D03 | yes | yes | 6.107 | - | - |
| CARD-D04 | yes | yes | 6.210 | - | - |
| CARD-D05 | no | no | 0.011 | submitted | the case names evidence this step cannot read: CARD-D05-FOLLOWUP |
| CARD-D06 | no | no | 8.141 | submitted | the intake supports no supported classification |
| CARD-D07 | no | no | 3.752 | submitted | BankReadError |
| CARD-D08 | yes | yes | 6.726 | - | - |
| CARD-D09 | no | no | 6.264 | submitted | the intake statement is not an exact excerpt of the intake |
| CARD-D10 | no | no | 3.295 | submitted | BankReadError |
| CARD-D11 | yes | yes | 6.209 | - | - |
| CARD-D12 | yes | yes | 6.724 | - | - |

## Failing cases

| Case | Exact failed check(s) | Reason |
|---|---|---|
| CARD-D05 | submitted | the case names evidence this step cannot read: CARD-D05-FOLLOWUP |
| CARD-D06 | submitted | the intake supports no supported classification |
| CARD-D07 | submitted | BankReadError |
| CARD-D09 | submitted | the intake statement is not an exact excerpt of the intake |
| CARD-D10 | submitted | BankReadError |

## Exceptions (proposed, pending pod agreement)

**Status: proposed. These exceptions are not agreed scope.** Each one is tied to a later ticket and is excluded only from the expected-failure list, never from the pass count.

| Case | Ticket | Failed checks | Note |
|---|---|---|---|
| CARD-D05 | COF-39 | submitted | A conflicting follow-up is not read, so the ambiguous conflict is not classified. Conflict and unsupported handling is COF-39. |
| CARD-D06 | COF-39 | submitted | An unsupported cash-withdrawal classification is not emitted. Conflict and unsupported handling is COF-39. |
| CARD-D07 | COF-40 | submitted | A persistent transaction failure stops the case instead of routing to manual_review with null facts. Retry and outage handling is COF-40. |
| CARD-D09 | COF-43 | submitted | The joined statement is not an exact intake excerpt, so the duplicate redelivery is not built. Duplicate intake and narrative work is COF-43. |
| CARD-D10 | COF-40 | submitted | A transient transaction fault is not retried, so the case is not built. Retry is COF-40. |

## Metered cost

Latency and cost come from `reports/scored-run-meters.json`, one row per case. The path is `deterministic_template`, so `model_calls`, `model_tokens_in` and `model_tokens_out` are 0 and the cost is exactly 0.00 USD. The meter records the calls the run actually made; it does not assume a model price.

| Case | Duration (ms) | Calls | Tokens in | Tokens out | Cost (USD) | Path |
|---|---|---|---|---|---|---|
| CARD-D01 | 8.838 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D02 | 6.818 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D03 | 6.107 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D04 | 6.210 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D05 | 0.011 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D06 | 8.141 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D07 | 3.752 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D08 | 6.726 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D09 | 6.264 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D10 | 3.295 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D11 | 6.209 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D12 | 6.724 | 0 | 0 | 0 | 0.00 | deterministic_template |

## Reproduce

Run from the worktree root on branch `kenmann01/cof-44-scored-run-across-all-twelve-cases`. `../../.venv` is the shared virtualenv of the enclosing checkout; from the primary checkout use `.venv\Scripts\python.exe`.

```sh
rm -f .state/cof44.sqlite3
../../.venv/Scripts/python.exe -m tools.runtime serve \
    --data data/dev --port 8899 --state .state/cof44.sqlite3 &
../../.venv/Scripts/python.exe tools/scored_run.py \
    --base-url http://127.0.0.1:8899 \
    --data data/dev \
    --gold feedback/dev_gold.json
```

The run exits 0 only when all twelve cases pass. A single transient fault fails once on a fresh state, so use a fresh state for each comparison.
