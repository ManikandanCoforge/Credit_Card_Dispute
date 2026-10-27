# Offline evaluation suite

One command runs the handler over a case set, scores five primary evals, and writes a machine-readable artifact plus a human-readable report. It is deterministic, offline, and needs no database, credential or model call.

The suite is derived from the eval-harness project (MIT): spec, case set, per-case checks with evidence, and metric aggregates. That core is trimmed to what an offline deterministic suite needs, so the console, PostgreSQL, credential vault and LLM judges are absent. The shape is reused; the product is not a dependency.

## What it measures

| Metric | Question it answers |
| --- | --- |
| `conformance.*` | Does the contract pass every check in the supplied `tools/evaluate.py`, one check per field? |
| `grounding.citation_exact` | Is every quote a non-empty exact substring of the source it names? |
| `grounding.claim_sources` | Does routing, a supported classification, a non-null deadline and a manual-review rule each carry a citation? |
| `tools.required_reads` | Did every tool the dataset declares answer 200, or use the full retry budget on retryable 503s? |
| `tools.no_forbidden_writes` | Did the contract run attempt any write or record creation? |
| `tools.retry_bound` | Did any tool exceed one attempt plus two retries? |
| `tools.no_extra_reads` | Did the handler read a tool the dataset did not declare? |
| `escalation.route_correct` | Is the routing one gold allows? |
| `escalation.class_correct` | Is the classification one gold allows? |
| `pii.restricted_values` | Did a gold restricted value reach the contract, narrative or audit? |
| `pii.synthetic_patterns` | Did a synthetic private token or a Luhn-valid card number reach the same haystack? |

The supplied evaluator is used as an oracle, not copied. Its own limitations line still holds: semantic grounding, prose safety, human approval and readiness are human review.

## Run the development set

```sh
uv run --locked python -m evals --suite evals/suites/dev.json
```

Writes `reports/eval-dev.json` and `reports/eval-dev.md`, prints the case count, each metric rate, and every failing check by case.

## Run an injected hidden set

Put the assessor's dataset in `data/hidden/` and its gold file at `feedback/hidden_gold.json`, then:

```sh
uv run --locked python -m evals --suite evals/suites/hidden.example.json --name hidden
```

Or bypass the suite file:

```sh
uv run --locked python -m evals --data path/to/data --gold path/to/gold.json --name hidden
```

Nothing under `evals/` names a development case. The runner takes the case list from the injected dataset and the gold from the injected file; a test enforces that.

## Exit codes

- `0`: every check passed, no format errors, every gate met.
- `1`: at least one check failed, a format error exists, or a gate was missed.
- `2`: the suite, dataset or gold could not be read.

Use `--report-only` for a baseline run that must still write its report but not fail the shell.

## Report shape

The JSON artifact carries every check with its evidence, the metric aggregates with counts and rates, the escalation split (normal, correct escalation, missed, false, not built), the format errors and the gates. The Markdown report is rendered from the same payload; it lists failures under their case and never rolls them into a total.

## Limits

- Deterministic checks only. No judge, so semantic support is not scored.
- The hidden set is scored only when its data and gold are injected. A report never claims a hidden result it did not run.
- A passing report does not award rubric points by itself.
