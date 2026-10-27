# Scored run across the twelve dev cases

Generated at 2026-10-27T23:18:22Z from commit `ac13f991d0c6db2c31def8025bc89e8cdac6ee91` against `http://127.0.0.1:8794`.
Dataset: `card-disputes-dev`.

## Result

- Pass: 9 / 12
- Format errors: 0
- p50 draft latency: 6.000 ms (nearest-rank over the latency_ms values in `reports/meters.jsonl`)
- p95 draft latency: 8.000 ms (nearest-rank over the latency_ms values in `reports/meters.jsonl`)
- Cost per case: 0.00 USD (0 model calls and 0 tokens in the meter file)
- Total cost: 0.00 USD

## Case results

| Case | Submitted | Passed | Duration (ms) | Failed checks | Error |
|---|---|---|---|---|---|
| CARD-D01 | yes | yes | 7.961 | - | - |
| CARD-D02 | yes | yes | 6.616 | - | - |
| CARD-D03 | yes | yes | 6.122 | - | - |
| CARD-D04 | yes | yes | 6.590 | - | - |
| CARD-D05 | yes | yes | 6.181 | - | - |
| CARD-D06 | yes | yes | 6.478 | - | - |
| CARD-D07 | no | no | 3.112 | submitted | BankReadError |
| CARD-D08 | yes | yes | 6.532 | - | - |
| CARD-D09 | no | no | 5.925 | submitted | the intake statement is not an exact excerpt of the intake |
| CARD-D10 | no | no | 3.279 | submitted | BankReadError |
| CARD-D11 | yes | yes | 6.249 | - | - |
| CARD-D12 | yes | yes | 6.067 | - | - |

## Failing cases

| Case | Exact failed check(s) | Reason |
|---|---|---|
| CARD-D07 | submitted | BankReadError |
| CARD-D09 | submitted | the intake statement is not an exact excerpt of the intake |
| CARD-D10 | submitted | BankReadError |

## Exceptions (proposed, pending pod agreement)

**Status: proposed. These exceptions are not agreed scope.** Each one is tied to a later ticket and is excluded only from the expected-failure list, never from the pass count.

| Case | Ticket | Failed checks | Note |
|---|---|---|---|
| CARD-D07 | COF-40 | submitted | A persistent transaction failure stops the case instead of routing to manual_review with null facts. Retry and outage handling is COF-40. |
| CARD-D09 | COF-43 | submitted | The joined statement is not an exact intake excerpt, so the duplicate redelivery is not built. Duplicate intake and narrative work is COF-43. |
| CARD-D10 | COF-40 | submitted | A transient transaction fault is not retried, so the case is not built. Retry is COF-40. |

## Metered cost

Cost comes from `reports/scored-run-meters.json`, one row per case. The p50 and p95 in the result section are read from `reports/meters.jsonl`, the redacted per-case meter file. The path is `deterministic_template`, so `model_calls`, `model_tokens_in` and `model_tokens_out` are 0 and the cost is 0.00 USD by construction: this run wires no model call, so the meter shows what the run did, not what a model would cost.

| Case | Duration (ms) | Calls | Tokens in | Tokens out | Cost (USD) | Path |
|---|---|---|---|---|---|---|
| CARD-D01 | 7.961 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D02 | 6.616 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D03 | 6.122 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D04 | 6.590 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D05 | 6.181 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D06 | 6.478 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D07 | 3.112 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D08 | 6.532 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D09 | 5.925 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D10 | 3.279 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D11 | 6.249 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D12 | 6.067 | 0 | 0 | 0 | 0.00 | deterministic_template |

## Reproduce

Run from the repository root, after `uv sync --locked`. The commands are the same on macOS, Linux and Windows. Use two terminals, and stop any other mock on port 8765 first.

In the first terminal, start the mock on a fresh state of its own:

```sh
uv run --locked python tools/runtime.py reset --confirm --state .state/scored-run.sqlite
uv run --locked python tools/runtime.py serve --data data/dev --port 8765 --state .state/scored-run.sqlite
```

In the second terminal, run every case and score it:

```sh
uv run --locked python tools/scored_run.py --base-url http://127.0.0.1:8765 --data data/dev --gold feedback/dev_gold.json --case-meters reports/meters.jsonl
```

The run exits 0 only when all twelve cases pass. A single transient fault fails once on a fresh state, so reset the state before each comparison. If the mock is not running, the run writes nothing and exits 1.
