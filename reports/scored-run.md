# Scored run across the twelve dev cases

Generated at 2026-10-26T01:44:33Z from commit `f50c1f48e0a3384bd04771c8a550c269fce9f2a7` against `http://127.0.0.1:8899`.
Dataset: `card-disputes-dev`.

## Result

- Pass: 7 / 12
- Format errors: 0
- p95 draft latency: 9.559 ms (nearest-rank over the measured durations)
- Cost per case: 0.00 USD (0 model calls and 0 tokens in the meter file)
- Total cost: 0.00 USD

## Case results

| Case | Submitted | Passed | Duration (ms) | Failed checks | Error |
|---|---|---|---|---|---|
| CARD-D01 | yes | yes | 8.528 | - | - |
| CARD-D02 | yes | yes | 8.873 | - | - |
| CARD-D03 | yes | yes | 8.855 | - | - |
| CARD-D04 | yes | yes | 8.899 | - | - |
| CARD-D05 | no | no | 0.017 | submitted | the case names evidence this step cannot read: CARD-D05-FOLLOWUP |
| CARD-D06 | no | no | 9.228 | submitted | the intake supports no supported classification |
| CARD-D07 | no | no | 4.832 | submitted | BankReadError |
| CARD-D08 | yes | yes | 8.289 | - | - |
| CARD-D09 | no | no | 9.559 | submitted | the intake statement is not an exact excerpt of the intake |
| CARD-D10 | no | no | 5.148 | submitted | BankReadError |
| CARD-D11 | yes | yes | 8.813 | - | - |
| CARD-D12 | yes | yes | 8.842 | - | - |

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

Latency and cost come from `reports/scored-run-meters.json`, one row per case. The path is `deterministic_template`, so `model_calls`, `model_tokens_in` and `model_tokens_out` are 0 and the cost is 0.00 USD by construction: this run wires no model call, so the meter shows what the run did, not what a model would cost.

| Case | Duration (ms) | Calls | Tokens in | Tokens out | Cost (USD) | Path |
|---|---|---|---|---|---|---|
| CARD-D01 | 8.528 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D02 | 8.873 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D03 | 8.855 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D04 | 8.899 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D05 | 0.017 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D06 | 9.228 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D07 | 4.832 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D08 | 8.289 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D09 | 9.559 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D10 | 5.148 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D11 | 8.813 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D12 | 8.842 | 0 | 0 | 0 | 0.00 | deterministic_template |

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
