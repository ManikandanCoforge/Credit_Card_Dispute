# Scored run across the twelve dev cases

Generated at 2026-10-27T22:00:28Z from commit `0e1be0449a0c96f20bc500c90c554c03b2ada04f` against `http://127.0.0.1:8765`.
Dataset: `card-disputes-dev`.

## Result

- Pass: 11 / 12
- Format errors: 0
- p95 draft latency: 3733.421 ms (nearest-rank over the measured durations)
- Cost per case: 0.00 USD (0 model calls and 0 tokens in the meter file)
- Total cost: 0.00 USD

## Case results

| Case | Submitted | Passed | Duration (ms) | Failed checks | Error |
|---|---|---|---|---|---|
| CARD-D01 | yes | yes | 15.211 | - | - |
| CARD-D02 | yes | yes | 17.124 | - | - |
| CARD-D03 | yes | yes | 18.228 | - | - |
| CARD-D04 | yes | yes | 15.781 | - | - |
| CARD-D05 | yes | yes | 16.331 | - | - |
| CARD-D06 | yes | yes | 16.858 | - | - |
| CARD-D07 | yes | yes | 3733.421 | - | - |
| CARD-D08 | yes | yes | 15.000 | - | - |
| CARD-D09 | no | no | 14.275 | submitted | the intake statement is not an exact excerpt of the intake |
| CARD-D10 | yes | yes | 1984.372 | - | - |
| CARD-D11 | yes | yes | 14.330 | - | - |
| CARD-D12 | yes | yes | 15.657 | - | - |

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
| CARD-D01 | 15.211 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D02 | 17.124 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D03 | 18.228 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D04 | 15.781 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D05 | 16.331 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D06 | 16.858 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D07 | 3733.421 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D08 | 15.000 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D09 | 14.275 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D10 | 1984.372 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D11 | 14.330 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D12 | 15.657 | 0 | 0 | 0 | 0.00 | deterministic_template |

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
