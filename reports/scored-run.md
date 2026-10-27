# Scored run across the twelve dev cases

Generated at 2026-10-27T22:29:38Z from commit `ce685eeba30394d1f50ab40da5687cf624c9ec7f` against `http://127.0.0.1:8792`.
Dataset: `card-disputes-dev`.

## Result

- Pass: 11 / 12
- Format errors: 0
- p95 draft latency: 4314.548 ms (nearest-rank over the measured durations)
- Cost per case: 0.00 USD (0 model calls and 0 tokens in the meter file)
- Total cost: 0.00 USD

## Case results

| Case | Submitted | Passed | Duration (ms) | Failed checks | Error |
|---|---|---|---|---|---|
| CARD-D01 | yes | yes | 20.380 | - | - |
| CARD-D02 | yes | yes | 44.724 | - | - |
| CARD-D03 | yes | yes | 29.604 | - | - |
| CARD-D04 | yes | yes | 36.751 | - | - |
| CARD-D05 | yes | yes | 31.562 | - | - |
| CARD-D06 | yes | yes | 32.220 | - | - |
| CARD-D07 | yes | yes | 4314.548 | - | - |
| CARD-D08 | yes | yes | 42.514 | - | - |
| CARD-D09 | no | no | 31.427 | submitted | the intake statement is not an exact excerpt of the intake |
| CARD-D10 | yes | yes | 1076.470 | - | - |
| CARD-D11 | yes | yes | 30.140 | - | - |
| CARD-D12 | yes | yes | 31.427 | - | - |

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
| CARD-D01 | 20.380 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D02 | 44.724 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D03 | 29.604 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D04 | 36.751 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D05 | 31.562 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D06 | 32.220 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D07 | 4314.548 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D08 | 42.514 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D09 | 31.427 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D10 | 1076.470 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D11 | 30.140 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D12 | 31.427 | 0 | 0 | 0 | 0.00 | deterministic_template |

## Reproduce

Run from the repository root, after `uv sync --locked`. The commands are the same on macOS, Linux and Windows. Use two terminals, and stop any other mock on port 8765 first.

In the first terminal, start the mock on a fresh state of its own:

```sh
uv run --locked python tools/runtime.py reset --confirm --state .state/scored-run.sqlite
uv run --locked python tools/runtime.py serve --data data/dev --port 8765 --state .state/scored-run.sqlite
```

In the second terminal, run every case and score it:

```sh
uv run --locked python tools/scored_run.py --base-url http://127.0.0.1:8765 --data data/dev --gold feedback/dev_gold.json
```

The run exits 0 only when all twelve cases pass. A single transient fault fails once on a fresh state, so reset the state before each comparison. If the mock is not running, the run writes nothing and exits 1.
