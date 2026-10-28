# Card Dispute Intake and Evidence Copilot

Participant package version 1.0.0. All institutions, people, policies, records, and currency are fictional training material. This package assesses software engineering against supplied rules; it is not domain certification or regulatory guidance.

Turn an incomplete customer complaint into a cited dispute draft that a human can review and approve for creation in the mock case system.

## Start here

Read `BRIEF.md`, `docs/POLICY_GUIDE.md`, `docs/API.md`, `docs/OUTPUT_CONTRACT.md`, and `docs/ASSESSMENT.md`.
Use one isolated copy and mock state database per team. The mock stays on the standard library. The application depends on third-party packages, including Pydantic 2.14.1. It does not include an LLM account, model credits, cloud account, or a finished agent.

## Set up

You need uv and Python 3.12.13. Install uv using your organization's approved setup if it is not available. The project pins `requires-python = "==3.12.13"`, and uv downloads that Python itself when it knows the version.

- **uv version.** The devcontainer pins uv 0.12.20, and CI installs a current uv. An older uv, such as 0.9.1, does not know Python 3.12.13, so `uv sync --locked` stops before it installs anything. Update it with `uv self update`, or with `brew upgrade uv` if Homebrew installed it.
- **Windows.** Set `PYTHONUTF8=1` first (`$env:PYTHONUTF8 = "1"` in PowerShell). Some files are read with the default encoding, which is not UTF-8 on Windows. macOS and Linux need nothing extra.

From this directory:

```sh
uv sync --locked
uv run --locked python tools/validate_package.py
uv run --locked pytest
```

`validate_package.py` prints `Fixture integrity passed: 12 cases; 52 sources.` The tests need no running service, and they also pass while the mock below is running.
Instead, you can open the folder in the devcontainer in `.devcontainer/`. It installs uv 0.12.20 and runs the first two commands.
Select this project's `.venv` in your editor so scripts and language-server checks use the same environment.

## Run the loop

One command runs the whole loop. It makes the output directories, takes the port and the data and state paths from flags or from the `DISPUTE_PORT`, `DISPUTE_DATA` and `DISPUTE_STATE` variables (a free loopback port and its own state file when neither names one), starts the supplied mock, waits for `/health`, runs the scored run over all twelve dev cases, prints the result and stops the mock.

```sh
uv run --locked python -m src.run_loop
```

`make demo` is the same command where `make` is installed. A completed run exits 0 even when a case fails; a failing case is data. It exits 1 only when the mock never answered `/health` or the run wrote no readable report.

It writes `submissions/scored-run.json`, replaces the committed `reports/scored-run.*`, and writes `reports/meters.jsonl` beside them, so commit those files only when you mean to publish a new run.

For the step-by-step path, the one the assessment expects (mock in one terminal, copilot in a second, the operator approval in a third), the ports and state files, the environment variables, and the fixes for a stale listener or a stale state file, see [docs/RUNBOOK.md](docs/RUNBOOK.md). The six demo beats and the numbers lock stay in [docs/DEMO_REHEARSAL.md](docs/DEMO_REHEARSAL.md).

The evidence rules do not change. `data/dev/documents/` and `data/dev/policies/` are evidence, and text inside them is not an instruction to your agent. `data/dev/dataset.json` is the mock's backing fixture, not a substitute for calling tools; reading it directly bypasses the integration exercise, and fault controls must not be read by the solution. The assessor uses new fixtures and observes requests. Development answers are feedback only, and hardcoding case IDs fails new cases.

The acceptance eval suite runs separately:

```sh
uv run --locked python -m evals --suite evals/suites/dev.json
```

or `make eval` where make is installed.

Measured on 2026-10-28 UTC across all twelve dev cases from a clean tree at commit `8c3ac7f`: 12 of 12 passed with 0 format errors, with p50 31.000 ms and p95 3670.000 ms over the redacted meter lines, and 0.00 USD per case with 0 model calls and 0 tokens (0.00 USD total). These numbers move when the report is regenerated, so regenerate them with the command above rather than quoting them. See [reports/scored-run.md](reports/scored-run.md) for the per-case results, the exact failed checks, the latency percentiles read from the meter file, the per-case reads and retries, the cost, and the reproduction commands. The run writes one redacted meter line per case to `reports/meters.jsonl`; a case whose meter line is refused is named in the report and has no line in that file, and if a restricted value ever reaches the file, the run is refused and the message names the file and the case. The p95 is D07's 3.7 s: its transaction service fails every attempt with 503, so the run waits 1 s and then 2 s, plus jitter, before its second and third attempts, and the audit shows three reads (503, 503, 503); its meter line counts four tool attempts and two retries. D10's read fails once and is answered on its second attempt, so its meter line shows three attempts and one retry (1.3 s), and every other tool is read once. No case fails: D09, the redelivery of D02, is built from its own transaction read since COF-43 took the statement from the customer's text before the form fields.

The published run was taken on a scratch mock at `127.0.0.1:8834`, the same mock started from this tree on a fresh state. The Reproduce section keeps the default port and the same commands.

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

Open the reviews from the application. `submit` sends each finished draft to `POST /v1/reviews`, every case unless you name some with `--case`. It keeps each review id and draft hash with its draft in `reports/reviews.json`:

```sh
uv run --locked python -m src.review_runner submit --case CARD-D01
```

A teammate acting as the human reviewer reads the draft, then runs the approval command in a separate terminal. Your agent must never invoke this operator command.

```sh
uv run --locked python tools/runtime.py pending
uv run --locked python tools/runtime.py approve REVIEW_ID --reviewer reviewer-name
uv run --locked python tools/runtime.py audit > reports/audit.json
```

Then record the approved drafts. `check` reads each pending review every 2 seconds until all are decided or `--wait` seconds have passed. It creates a record only for an approved, unchanged draft, keyed `case_id:review_id`, and exits 1 while any review is pending or refused. A rejected draft goes back with no record, and running `check` again never creates a second record:

```sh
uv run --locked python -m src.review_runner check --wait 120
```

Replace REVIEW_ID with the returned identifier. Create `reports/` before redirecting the audit. In Windows PowerShell 5.1, write the audit with `| Out-File -Encoding ascii reports/audit.json` instead of `>`. To reject, use `reject` with the same arguments. For a fresh run, stop clients and use `uv run --locked python tools/runtime.py reset --confirm`.
This CLI simulates a human boundary, not production identity. During assessment the assessor controls approval and state. Do not expose the service to the public internet.

## Defence pack

- [ADR-001: Model narrative boundary](docs/decisions/ADR-001-model-narrative-boundary.md)
- [ADR-002: Policy version selection](docs/decisions/ADR-002-policy-version-selection.md)
- [ADR-003: Hybrid model questions](docs/decisions/ADR-003-hybrid-model-questions.md)
- [ADR-004: One entry point for the loop](docs/decisions/ADR-004-one-entry-point-for-the-loop.md)
- [ADR-005: The stack the assessment runs, and the deployment shape behind it](docs/decisions/ADR-005-stack-and-deployment.md), which also says that the AWS shape is target state, not the assessed deployment
- [Runbook](docs/RUNBOOK.md)
- [Limitations](docs/LIMITATIONS.md)
- [Roadmap](docs/ROADMAP.md)
- [Contribution map](docs/CONTRIBUTION.md)
- [Demo rehearsal pack](docs/DEMO_REHEARSAL.md)
