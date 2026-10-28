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

The scored run also applies `pii.artifact_checks` to `reports/meters.jsonl`, the redacted per-case meter file. The same detectors run over each line, and a leak refuses the run with the file and the case named.

## Run the development set

```sh
uv run --locked python -m evals --suite evals/suites/dev.json
```

Writes `reports/eval-dev.json` and `reports/eval-dev.md`, prints the case count, each metric rate, and every failing check by case. The committed `reports/eval-dev.md` cites `8553bb3` and 12 of 12, with every metric at 100%.

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

Our own fixtures are not that set. The assessor dataset and gold are absent before the defence, so this repository publishes no hidden-set score. The closest published estimate is the fixture results below and `reports/hybrid-eval.json`; `docs/LIMITATIONS.md` says what the panel should read from them.

## Exit codes

- `0`: every check passed, no format errors, every gate met.
- `1`: at least one check failed, a format error exists, or a gate was missed.
- `2`: the suite, dataset or gold could not be read.

Use `--report-only` for a baseline run that must still write its report but not fail the shell.

## Report shape

The JSON artifact carries every check with its evidence, the metric aggregates with counts and rates, the escalation split (normal, correct escalation, missed, false, not built), the format errors and the gates. The Markdown report is rendered from the same payload; it lists failures under their case and never rolls them into a total.

## Limits

- Deterministic checks only. No judge, so semantic support is not scored.
- The hidden set is scored only when its data and gold are injected. A report never claims a hidden result it did not run. The fixture runs above are our proxy, not the assessor set; `docs/LIMITATIONS.md` states the estimate they support.
- A passing report does not award rubric points by itself.

## Evaluation assets for the hybrid

Everything in this folder supports [ADR-003](../docs/decisions/ADR-003-hybrid-model-questions.md). The application never reads it at run time. `models.toml`, at the repository root, is the only model file the application reads.

### Fixture suites: `fixtures/`

| Suite | Cases | What it covers |
|---|---|---|
| `synth` | 31 | Paraphrases of each type, policy-window edges, tool faults, conflicts, missing evidence, injection, a restricted token, a duplicate redelivery and a non-ASCII merchant |
| `stress` | 16 | Wording the rules miss for each type, cash without "ATM", a fee, an overcharge, vague complaints that should get no type, injection and negation traps, and two problems in one |
| `holdout` | 8 | New wording and traps: negations, injection addressed to a model or hidden in an attachment, cash without a keyword, and two problems in one |

### Latest deterministic results

Offline suite, five primary evals, branch HEAD `8553bb3`, 2026-10-28 UTC. Both runs exit `1` and report no format error; each artifact lists every failing check with its evidence.

| Suite | Cases | Fully passed | Failing cases | Artifact |
|---|---|---|---|---|
| `holdout` | 8 | 3 | `HLD-H01`, `HLD-H05`, `HLD-H06`, `HLD-H07`, `HLD-H08` | [`eval-holdout.md`](reports/eval-holdout.md) |
| `stress` | 16 | 4 | `STR-P03`, `STR-P05` to `STR-P12`, `STR-P13`, `STR-P14`, `STR-P15` | [`eval-stress.md`](reports/eval-stress.md) |

The supplied bank evaluator scores the same cases higher with recorded model answers: 4 of 8 holdout and 16 of 16 stress in `reports/hybrid-eval.json`. Its rules-alone row uses that evaluator too (3 of 8 and 5 of 16), not these five evals, so the two tables are not one progression: the offline suite also requires a manual-review-rule citation, which is why `STR-P13` fails here and not there. `synth` is not rerun here; its rows are in the hybrid report.

The failures are those numbers, not the counts alone. HLD-H01 is routed `manual_review` where the gold expects `service_not_received`. HLD-H05 stops at intake with `expected exactly one 'Amount:' line in the source`, and HLD-H06 to HLD-H08 stop because the intake supports no supported classification. On stress, STR-P03 and STR-P05 to STR-P12 and STR-P14 stop for the same reason, STR-P13 misses the manual-review-rule citation, and STR-P15 is typed as a duplicate where the gold expects an ambiguous escalation. The artifacts carry every failing check with its evidence.

Reproduce both runs from the repository root:

```sh
uv run --locked python -m evals --suite evals/suites/dev.json --data evals/fixtures/holdout/data --gold evals/fixtures/holdout/gold.json --name holdout --out evals/reports/eval-holdout
uv run --locked python -m evals --suite evals/suites/dev.json --data evals/fixtures/stress/data --gold evals/fixtures/stress/gold.json --name stress --out evals/reports/eval-stress
```

Each suite's `data/` is in the package's own format: `dataset.json`, `documents/` and `policies/`. The unmodified mock serves it. `gold.json` follows the bank evaluator's format, and `CASES.md` lists what each case tests and the assumption its expected answer rests on.

The suites come unchanged from the Card Disputes Copilot assessment, and their expected answers were written before any run. They follow the copilot's assumption log. Where this team decides an assumption differently, that case's expected answer is a question for the pod, not a requirement. One example is a reported date that is not an ISO date.

Check that a suite is consistent. `PYTHONUTF8=1` matters on Windows, because one merchant name is not ASCII.

```sh
PYTHONUTF8=1 uv run --locked python -c "from pathlib import Path; from tools.validate_package import validate; [validate(Path('evals/fixtures', s, 'data')) for s in ('synth', 'stress', 'holdout')]"
```

### Qualification sets: `qualification/`

These are the sets a model must pass before `models.toml` may list it. The README in that folder gives the sets, the bar and each run's result.

### Recordings: `recordings/`

`gpt-6-luna.jsonl` holds 41 answers from GPT-6 Luna on Azure OpenAI (East US) to 40 distinct questions. SYN-S28 and SYN-S29 ask the same question, and both answers agree.

- 15 dispute-type answers
- 26 two-problem answers

They come from the copilot's registered Week 10 runs of 25 October, one trace per suite. Each answer was replayed through this repository's pipeline against the unmodified mock. It was kept only when the prompt this code sends is byte-for-byte the prompt Luna was sent, matched by prompt hash.

In the current evaluation this code asks 51 questions. Ten of them were not asked in that run, so they have no recording and replay as no answer:

- 3 dispute-type questions: SYN-S03, HLD-H07 and HLD-H08
- 7 two-problem questions: CARD-D08, CARD-D10, SYN-S14, SYN-S17, SYN-S20, SYN-S24 and SYN-S25

CARD-D10 and SYN-S14 are asked now because the tool reads retry (COF-40): in the recorded runs a tool fault stopped both cases before any question.

Each line holds three things:

- the request key: a sha256 of the system prompt, user message and schema, as canonical JSON
- the answer
- the call meter: provider, model, latency and tokens

A line never holds the prompt, the customer's lines or a credential.

A recording is valid only for the prompt version it was made with. A prompt or schema change makes every key miss, so an old answer is never reused for a new question.

To make a new recording, run a live model that is qualified and approved in `models.toml`, with `MODEL_RECORD` naming a new file. Its folder must already exist. Name the file after the model, because the replay reports the file name as the model. A recording is appended to, so start from a file that does not exist yet, and replace the committed recording in its own pull request.

```sh
MODEL_PROVIDER=azure_openai MODEL_ID=gpt-6-luna AZURE_OPENAI_ENDPOINT=https://RESOURCE.openai.azure.com AZURE_OPENAI_API_KEY=KEY MODEL_RECORD=evals/recordings/new/gpt-6-luna.jsonl uv run --locked --with openai==3.37.0 python tools/hybrid_eval.py
```

### Hybrid evaluation report: `reports/hybrid-eval.json`

`tools/hybrid_eval.py` runs each suite twice, each time on a fresh copy of the unmodified mock: first the rules alone, then the hybrid. The bank's evaluator scores both runs. The report gives, for each suite and design:

- passed cases, and the failed checks of each case that failed
- wrong drafts marked ready
- cases sent to manual review
- cases not built, with the reason for each
- model calls and tokens

Reproduce it from the recording, with no network and no credentials:

```sh
PYTHONUTF8=1 MODEL_PROVIDER=replay MODEL_REPLAY=evals/recordings/gpt-6-luna.jsonl uv run --locked python tools/hybrid_eval.py
```

Results on 2026-10-28 UTC:

| Suite | Rules alone | Hybrid | Wrong drafts marked ready (rules → hybrid) | Model calls | Tokens in / out |
|---|---|---|---|---|---|
| dev (12) | 12 | 12 | 0 → 0 | 7 | 705 / 174 |
| synth (31) | 19 | 23 | 3 → 3 | 23 | 3,528 / 572 |
| stress (16) | 5 | 16 | 1 → 0 | 16 | 5,585 / 647 |
| holdout (8) | 3 | 4 | 0 → 0 | 5 | 747 / 133 |
| Total (67) | 39 | 55 | 4 → 3 | 51 | 10,565 / 1,526 |

Rerunning the replay command above on this tree reproduces the table exactly, and the checked-in report is that output. ADR-003 explains the cases that still fail. The token counts are Luna's own counts for these exact prompts, recorded on 25 October.
