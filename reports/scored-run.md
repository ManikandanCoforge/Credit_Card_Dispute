# Scored run across the twelve dev cases

Generated at 2026-10-27T14:48:48Z from commit `14b15241c35da29152c89c1b76eec7ee22b05280` against `http://127.0.0.1:8899`.
Dataset: `card-disputes-dev`.

## Result

- Pass: 11 / 12
- Format errors: 0
- p95 draft latency: 3446.281 ms (nearest-rank over the measured durations)
- Cost per case: 0.00 USD (0 model calls and 0 tokens in the meter file)
- Total cost: 0.00 USD

## Case results

| Case | Submitted | Passed | Duration (ms) | Failed checks | Error |
|---|---|---|---|---|---|
| CARD-D01 | yes | yes | 21.263 | - | - |
| CARD-D02 | yes | yes | 19.155 | - | - |
| CARD-D03 | yes | yes | 19.873 | - | - |
| CARD-D04 | yes | yes | 19.643 | - | - |
| CARD-D05 | yes | yes | 20.526 | - | - |
| CARD-D06 | yes | yes | 19.249 | - | - |
| CARD-D07 | yes | yes | 3446.281 | - | - |
| CARD-D08 | yes | yes | 19.050 | - | - |
| CARD-D09 | no | no | 18.272 | submitted | the intake statement is not an exact excerpt of the intake |
| CARD-D10 | yes | yes | 1484.545 | - | - |
| CARD-D11 | yes | yes | 17.893 | - | - |
| CARD-D12 | yes | yes | 21.753 | - | - |

## Failing cases

| Case | Exact failed check(s) | Reason |
|---|---|---|
| CARD-D09 | submitted | the intake statement is not an exact excerpt of the intake |

## Exceptions (proposed, pending pod agreement)

**Status: proposed. These exceptions are not agreed scope.** Each one is tied to a later ticket and is excluded only from the expected-failure list, never from the pass count.

| Case | Ticket | Failed checks | Note |
|---|---|---|---|
| CARD-D09 | COF-43 | submitted | The joined statement is not an exact intake excerpt, so the duplicate redelivery is not built. Duplicate intake and narrative work is COF-43. |

## Metered cost

Latency and cost come from `reports/scored-run-meters.json`, one row per case. The path is `deterministic_template`, so `model_calls`, `model_tokens_in` and `model_tokens_out` are 0 and the cost is 0.00 USD by construction: this run wires no model call, so the meter shows what the run did, not what a model would cost.

| Case | Duration (ms) | Calls | Tokens in | Tokens out | Cost (USD) | Path |
|---|---|---|---|---|---|---|
| CARD-D01 | 21.263 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D02 | 19.155 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D03 | 19.873 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D04 | 19.643 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D05 | 20.526 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D06 | 19.249 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D07 | 3446.281 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D08 | 19.050 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D09 | 18.272 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D10 | 1484.545 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D11 | 17.893 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D12 | 21.753 | 0 | 0 | 0 | 0.00 | deterministic_template |

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
