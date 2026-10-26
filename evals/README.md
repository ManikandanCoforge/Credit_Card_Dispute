# Evaluation assets for the hybrid

Everything in this folder supports [ADR-003](../docs/decisions/ADR-003-hybrid-model-questions.md). The application never reads it at run time. `models.toml`, at the repository root, is the only model file the application reads.

## Fixture suites: `fixtures/`

| Suite | Cases | What it covers |
|---|---|---|
| `synth` | 31 | Paraphrases of each type, policy-window edges, tool faults, conflicts, missing evidence, injection, a restricted token, a duplicate redelivery and a non-ASCII merchant |
| `stress` | 16 | Wording the rules miss for each type, cash without "ATM", a fee, an overcharge, vague complaints that should get no type, injection and negation traps, and two problems in one |
| `holdout` | 8 | New wording and traps: negations, injection addressed to a model or hidden in an attachment, cash without a keyword, and two problems in one |

Each suite's `data/` is in the package's own format: `dataset.json`, `documents/` and `policies/`. The unmodified mock serves it. `gold.json` follows the bank evaluator's format, and `CASES.md` lists what each case tests and the assumption its expected answer rests on.

The suites come unchanged from the Card Disputes Copilot assessment, and their expected answers were written before any run. They follow the copilot's assumption log. Where this team decides an assumption differently, that case's expected answer is a question for the pod, not a requirement. One example is a reported date that is not an ISO date.

Check that a suite is consistent. `PYTHONUTF8=1` matters on Windows, because one merchant name is not ASCII.

```sh
PYTHONUTF8=1 uv run --locked python -c "from pathlib import Path; from tools.validate_package import validate; [validate(Path('evals/fixtures', s, 'data')) for s in ('synth', 'stress', 'holdout')]"
```

## Qualification sets: `qualification/`

These are the sets a model must pass before `models.toml` may list it. The README in that folder gives the sets, the bar and each run's result.

## Recordings: `recordings/`

`gpt-6-luna.jsonl` holds 41 answers from GPT-6 Luna on Azure OpenAI (East US) to 40 distinct questions. SYN-S28 and SYN-S29 ask the same question, and both answers agree.

- 15 dispute-type answers
- 26 two-problem answers

They come from the copilot's registered Week 10 runs of 25 October, one trace per suite. Each answer was replayed through this repository's pipeline against the unmodified mock. It was kept only when the prompt this code sends is byte-for-byte the prompt Luna was sent, matched by prompt hash.

In the current evaluation this code asks 48 questions. Eight of them were not asked in that run, so they have no recording and replay as no answer:

- 3 dispute-type questions: SYN-S03, HLD-H07 and HLD-H08
- 5 two-problem questions: CARD-D08, SYN-S17, SYN-S20, SYN-S24 and SYN-S25

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

## Hybrid evaluation report: `reports/hybrid-eval.json`

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

Results on 2026-10-26:

| Suite | Rules alone | Hybrid | Wrong drafts marked ready (rules → hybrid) | Model calls | Tokens in / out |
|---|---|---|---|---|---|
| dev (12) | 9 | 9 | 0 → 0 | 5 | 544 / 132 |
| synth (31) | 15 | 19 | 3 → 3 | 22 | 3,528 / 572 |
| stress (16) | 5 | 16 | 1 → 0 | 16 | 5,585 / 647 |
| holdout (8) | 3 | 4 | 0 → 0 | 5 | 747 / 133 |
| Total (67) | 32 | 48 | 4 → 3 | 48 | 10,404 / 1,484 |

ADR-003 explains the cases that still fail. The token counts are Luna's own counts for these exact prompts, recorded on 25 October.
