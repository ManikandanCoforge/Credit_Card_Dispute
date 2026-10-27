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

Measured on 2026-10-27 across all twelve dev cases from a clean tree at commit `14b1524`: 11 of 12 passed with 0 format errors. Regenerate them with the command in the report rather than quoting them. See [reports/scored-run.md](reports/scored-run.md) for the per-case results, the exact failed checks, the p95 latency and cost from the meter file, and the reproduction commands. The p95 is D07's: its transaction service never answers, so the run waits about 1s and then 2s between its three attempts. The one failure, D09, is a proposed exception tied to COF-43, pending pod agreement.

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

Replace REVIEW_ID with the returned identifier. Create `reports/` before redirecting the audit. To reject, use `reject` with the same arguments. For a fresh run, stop clients and use `uv run --locked python tools/runtime.py reset --confirm`.
This CLI simulates a human boundary, not production identity. During assessment the assessor controls approval and state. Do not expose the service to the public internet.

## Defence pack

- [ADR-001: Model narrative boundary](docs/decisions/ADR-001-model-narrative-boundary.md)
- [ADR-002: Policy version selection](docs/decisions/ADR-002-policy-version-selection.md)
- [Limitations](docs/LIMITATIONS.md)
- [Roadmap](docs/ROADMAP.md)
- [Contribution map](docs/CONTRIBUTION.md)
- [Demo rehearsal pack](docs/DEMO_REHEARSAL.md)
