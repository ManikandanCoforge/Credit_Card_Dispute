# Scored run across the twelve dev cases

Generated at 2026-10-28T00:07:58Z from commit `3a747a58cc8255e47a4a47f17794a1f764354bf1` against `http://127.0.0.1:8792`.
Dataset: `card-disputes-dev`.

## Result

- Pass: 11 / 12
- Format errors: 0
- p50 draft latency: 31.000 ms (nearest-rank over the latency_ms values in `reports/meters.jsonl`)
- p95 draft latency: 3444.000 ms (nearest-rank over the latency_ms values in `reports/meters.jsonl`)
- Cost per case: 0.00 USD (0 model calls and 0 tokens in the meter file)
- Total cost: 0.00 USD

## Case results

| Case | Submitted | Passed | Duration (ms) | Failed checks | Error |
|---|---|---|---|---|---|
| CARD-D01 | yes | yes | 36.758 | - | - |
| CARD-D02 | yes | yes | 30.742 | - | - |
| CARD-D03 | yes | yes | 32.389 | - | - |
| CARD-D04 | yes | yes | 30.111 | - | - |
| CARD-D05 | yes | yes | 31.654 | - | - |
| CARD-D06 | yes | yes | 18.819 | - | - |
| CARD-D07 | yes | yes | 3444.654 | - | - |
| CARD-D08 | yes | yes | 30.781 | - | - |
| CARD-D09 | no | no | 29.805 | submitted | the intake statement is not an exact excerpt of the intake |
| CARD-D10 | yes | yes | 1728.030 | - | - |
| CARD-D11 | yes | yes | 32.544 | - | - |
| CARD-D12 | yes | yes | 32.563 | - | - |

## Reads and retries

Attempts and retries are read from the run's own meter file `reports/meters.jsonl`. A case with no meter line shows a dash.

| Case | Tool attempts | Retries | Meter error |
|---|---|---|---|
| CARD-D01 | 2 | 0 | - |
| CARD-D02 | 2 | 0 | - |
| CARD-D03 | 2 | 0 | - |
| CARD-D04 | 2 | 0 | - |
| CARD-D05 | 2 | 0 | - |
| CARD-D06 | 2 | 0 | - |
| CARD-D07 | 4 | 2 | - |
| CARD-D08 | 2 | 0 | - |
| CARD-D09 | 2 | 0 | - |
| CARD-D10 | 3 | 1 | - |
| CARD-D11 | 2 | 0 | - |
| CARD-D12 | 2 | 0 | - |

Every case except CARD-D07, CARD-D10 reads each tool once; those are the only rows with a retry.

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

Cost comes from `reports/scored-run-meters.json`, one row per case. The p50 and p95 in the result section are read from `reports/meters.jsonl`, the redacted per-case meter file. The path is `deterministic_template`, so `model_calls`, `model_tokens_in` and `model_tokens_out` are 0 and the cost is 0.00 USD by construction: this run wires no model call, so the meter shows what the run did, not what a model would cost.

| Case | Duration (ms) | Calls | Tokens in | Tokens out | Cost (USD) | Path |
|---|---|---|---|---|---|---|
| CARD-D01 | 36.758 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D02 | 30.742 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D03 | 32.389 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D04 | 30.111 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D05 | 31.654 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D06 | 18.819 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D07 | 3444.654 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D08 | 30.781 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D09 | 29.805 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D10 | 1728.030 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D11 | 32.544 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D12 | 32.563 | 0 | 0 | 0 | 0.00 | deterministic_template |

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
