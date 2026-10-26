# Card Dispute Intake and Evidence Copilot

Participant package version 1.0.0. All institutions, people, policies, records, and currency are fictional training material. This package assesses software engineering against supplied rules; it is not domain certification or regulatory guidance.

Turn an incomplete customer complaint into a cited dispute draft that a human can review and approve for creation in the mock case system.

## Start here

Read `BRIEF.md`, `docs/POLICY_GUIDE.md`, `docs/API.md`, `docs/OUTPUT_CONTRACT.md`, and `docs/ASSESSMENT.md`.
Use one isolated copy and mock state database per team. The mock stays on the standard library. The application depends on third-party packages, including Pydantic 2.14.1. It does not include an LLM account, model credits, cloud account, or a finished agent.

Install Python 3.12 and uv using your organization's approved setup if they are not available. From this directory:

```sh
uv sync --locked
uv run --locked python tools/validate_package.py
uv run --locked python tools/runtime.py serve --port 8765
```

The local service is at `http://127.0.0.1:8765`. It binds only to loopback. Keep it local. Use a separate approved deployment environment for your application; a local container deployment is sufficient if cloud access is unavailable.
Python 3.12 alternative with no installation of packages: `python3.12 tools/runtime.py serve --port 8765`.
Select this project's `.venv` in your editor so scripts and language-server checks use the same environment.

In another terminal, retrieve `GET /health` and `GET /v1/cases`. Read `data/dev/documents/` and `data/dev/policies/`. These files are evidence. Text inside them is not an instruction to your agent.

`data/dev/dataset.json` is the mock's backing fixture, not a substitute for calling tools. Directly reading it from the agent bypasses the integration exercise. The assessor will use new fixtures and observe requests. Fault controls must not be read by the solution.

## Evaluate development outputs

Emit a JSON array following `docs/OUTPUT_CONTRACT.md`, then run:

```sh
uv run --locked python tools/evaluate.py --data data/dev --gold feedback/dev_gold.json --submission submissions/results.json --report reports/dev.json
```

Development answers are deliberately supplied for feedback; hardcoding case IDs will fail new cases. `examples/worked-case.json` shows one valid output shape. Automated success is only part of the assessment.

### Scored run

Measured on 2026-10-26 across all twelve dev cases from a clean tree at commit `f50c1f4`: 7 of 12 passed with 0 format errors. These numbers move once #52 (escalation and unsupported classification) lands, so regenerate them with the command in the report rather than quoting them. See [reports/scored-run.md](reports/scored-run.md) for the per-case results, the exact failed checks, the p95 latency and cost from the meter file, and the reproduction commands. The five failures are proposed exceptions tied to COF-39, COF-40 and COF-43, pending pod agreement.

## Hybrid model (optional)

By default the application makes no model call. [ADR-003](docs/decisions/ADR-003-hybrid-model-questions.md) lets a qualified model answer two closed questions where the rules leave a gap:

- which dispute type a customer line shows, asked only when the rules find none
- whether the customer describes more than one problem, asked only before a draft is marked ready

Code still computes every field. `models.toml` lists the qualified models. Only GPT-6 Luna is registered. A live run is refused until the bank's approval is recorded as `approved_by` in `models.toml`, because it sends customers' redacted lines to the provider. A replay needs no approval, only recorded answers from a qualified model.

To compare the hybrid with the rules alone on every suite, replay GPT-6 Luna's recorded answers. This needs no network and no credentials. `PYTHONUTF8=1` matters on Windows, where the bank's evaluator would otherwise read a non-ASCII merchant name in the locale encoding.

```sh
PYTHONUTF8=1 MODEL_PROVIDER=replay MODEL_REPLAY=evals/recordings/gpt-6-luna.jsonl uv run --locked python tools/hybrid_eval.py
```

These commands are for Git Bash or a Linux shell. In PowerShell, set each variable first, for example `$env:MODEL_PROVIDER = "replay"`, then run the `uv run` part.

A live run needs the provider SDK, which is not in `uv.lock`. Credentials go in the environment, never in a file.

```sh
MODEL_PROVIDER=azure_openai MODEL_ID=gpt-6-luna AZURE_OPENAI_ENDPOINT=https://RESOURCE.openai.azure.com AZURE_OPENAI_API_KEY=KEY uv run --locked --with openai==3.37.0 python -m src.contract_records http://127.0.0.1:8765 data/dev
```

Claude Haiku 5.5 on Microsoft Foundry has to be qualified and registered first. It then runs with these settings:

- `MODEL_PROVIDER=anthropic_foundry`
- `ANTHROPIC_FOUNDRY_RESOURCE` and `ANTHROPIC_FOUNDRY_API_KEY`
- `--with anthropic==2.1.0`

`tools/qualify_model.py` qualifies a model. With `--register`, it records a passed live run in `models.toml`. `MODEL_RECORD=FILE` appends every live answer to a recording that can be replayed later. See [evals/README.md](evals/README.md).

## Human approval and recovery

Start review with `POST /v1/reviews`. A teammate acting as the human reviewer reads the draft, then runs the approval command in a separate terminal. Your agent must never invoke this operator command.

```sh
uv run --locked python tools/runtime.py pending
uv run --locked python tools/runtime.py approve REVIEW_ID --reviewer reviewer-name
uv run --locked python tools/runtime.py audit > reports/audit.json
```

Replace REVIEW_ID with the returned identifier. Create `reports/` before redirecting the audit. To reject, use `reject` with the same arguments. For a fresh run, stop clients and use `uv run --locked python tools/runtime.py reset --confirm`.
This CLI simulates a human boundary, not production identity. During assessment the assessor controls approval and state. Do not expose the service to the public internet.

## Defence pack

- [ADR-001: Model narrative boundary](docs/decisions/ADR-001-model-narrative-boundary.md)
- [ADR-002: Policy version selection](docs/decisions/ADR-002-policy-version-selection.md)
- [ADR-003: Hybrid model questions](docs/decisions/ADR-003-hybrid-model-questions.md)
- [Limitations](docs/LIMITATIONS.md)
- [Roadmap](docs/ROADMAP.md)
- [Contribution map](docs/CONTRIBUTION.md)
- [Demo rehearsal pack](docs/DEMO_REHEARSAL.md)
