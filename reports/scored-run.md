# Scored run across the twelve dev cases

Generated at 2026-10-28T02:10:46Z from commit `8c3ac7f4859c0ec9c36a51ef26e78451a46c2889` against `http://127.0.0.1:8834`.
Dataset: `card-disputes-dev`.

## Result

- Pass: 12 / 12
- Format errors: 0
- p50 draft latency: 31.000 ms (nearest-rank over the latency_ms values in `reports/meters.jsonl`)
- p95 draft latency: 3670.000 ms (nearest-rank over the latency_ms values in `reports/meters.jsonl`)
- Cost per case: 0.00 USD (0 model calls and 0 tokens in the meter file)
- Total cost: 0.00 USD

## Case results

| Case | Submitted | Passed | Duration (ms) | Failed checks | Error |
|---|---|---|---|---|---|
| CARD-D01 | yes | yes | 31.976 | - | - |
| CARD-D02 | yes | yes | 30.195 | - | - |
| CARD-D03 | yes | yes | 9.472 | - | - |
| CARD-D04 | yes | yes | 20.359 | - | - |
| CARD-D05 | yes | yes | 31.046 | - | - |
| CARD-D06 | yes | yes | 30.957 | - | - |
| CARD-D07 | yes | yes | 3670.626 | - | - |
| CARD-D08 | yes | yes | 20.172 | - | - |
| CARD-D09 | yes | yes | 30.130 | - | - |
| CARD-D10 | yes | yes | 1290.001 | - | - |
| CARD-D11 | yes | yes | 33.483 | - | - |
| CARD-D12 | yes | yes | 43.976 | - | - |

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

None. Every case passed.

## Exceptions (proposed, pending pod agreement)

**Status: proposed. These exceptions are not agreed scope.** Each one is tied to a later ticket and is excluded only from the expected-failure list, never from the pass count.

None. No failing case has a proposed ticket.

## Metered cost

Cost comes from `reports/scored-run-meters.json`, one row per case. The p50 and p95 in the result section are read from `reports/meters.jsonl`, the redacted per-case meter file. The path is `deterministic_template`, so `model_calls`, `model_tokens_in` and `model_tokens_out` are 0 and the cost is 0.00 USD by construction: this run wires no model call, so the meter shows what the run did, not what a model would cost.

| Case | Duration (ms) | Calls | Tokens in | Tokens out | Cost (USD) | Path |
|---|---|---|---|---|---|---|
| CARD-D01 | 31.976 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D02 | 30.195 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D03 | 9.472 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D04 | 20.359 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D05 | 31.046 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D06 | 30.957 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D07 | 3670.626 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D08 | 20.172 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D09 | 30.130 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D10 | 1290.001 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D11 | 33.483 | 0 | 0 | 0 | 0.00 | deterministic_template |
| CARD-D12 | 43.976 | 0 | 0 | 0 | 0.00 | deterministic_template |

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
