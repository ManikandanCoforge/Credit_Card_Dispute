# ADR-005: The stack the assessment runs, and the deployment shape behind it

- Status: Accepted
- Date: 2026-10-28
- Ticket: COF-34 (#34), Week 11 rubric Part 1
- Owner: Ken (kenmann01)
- Related: `pyproject.toml`, `tools/runtime.py`, `src/run_loop.py`, `src/observability.py`, `src/span_store/`, `deploy/poc/`, `docs/ASSESSMENT.md`

## Context

The rubric asks for one recorded stack decision naming the framework, the data
layer, the deployment target and the evaluation tooling. Four records existed
and none of them answered all four questions:

- `ADR-001` to `ADR-004` each decide one seam (the model boundary, policy
  selection, hybrid questions, the loop entry point), not the stack.
- `docs/aws-architecture-services.md` describes AWS as a target state. It does
  not say what the assessed run executes on, so a reader can mistake the target
  state for the deployed system.
- `deploy/` held a working Dockerfile, a serve script and a Terraform stack,
  untracked, so the story lived only on the author's disk.
- `README.md` names the commands, not the choice behind them.

This ADR fixes the first record. It is deliberately about the assessed system,
because `docs/ASSESSMENT.md` scores the loopback run and the audit trail, not a
cloud deployment.

## Decision

The assessed stack is Python 3.12 and the standard library, with no web
framework, on a single machine, against a supplied mock bank that speaks HTTP.

1. **Runtime and framework.** Python 3.12, one process. The product is the
   prepare-and-record pipeline (`src/app.py` `prepare_complaints`), not a
   server: it calls the bank's HTTP API with `urllib.request`
   (`src/run_loop.py:27`) and the supplied harness serves that API with
   `http.server.ThreadingHTTPServer` (`tools/runtime.py:170`). No Flask, no
   FastAPI, no WSGI or ASGI layer. `uv.lock` holds the tools the gate needs,
   not a web framework.
2. **Data layer.** Two file-backed stores and one remote store:
   - JSON datasets: `data/dev` for the cases, `feedback/dev_gold.json` for
     expectations, `evals/suites/` for the evaluation suites. Read-only inputs.
   - SQLite: the mock bank's state file (`BANK_STATE` in the container
     wrapper, `--state` in the assessed mock, default `.state/mock.sqlite`)
     holds records, reviews and their approval binding,
     so the audit trail survives a restart; the trace store
     (`src/observability.py:241`, `TRACE_DB` default
     `.state/traces.sqlite3`) holds finished spans through the `SpanStore`
     Protocol in `src/span_store/base.py` with `src/span_store/sqlite.py` as the
     adapter. No ORM and no second database process.
   - Records are written to the bank over HTTP, never to a local table. The
     authoritative audit trail is the bank's store; the run's copies in
     `reports/` are evidence, not the source of truth.
3. **Deployment target.** The assessed deployment is loopback: one command
   starts the mock on a free port, runs the pipeline, writes `reports/` and
   stops the mock (`ADR-004`). That is the shape the demo and the rubric use.
   The AWS target state is committed in `deploy/poc`: `Dockerfile`
   (`python:3.12-slim`), `serve.py`, `deploy.sh` and Terraform for one ECR
   repository, one ECS Fargate service, one ALB and two IAM roles
   (`deploy/poc/terraform/README.md`). It has **not been applied**; the
   Terraform README says so, and this ADR repeats it. It is target state for a
   pilot, not the assessed deployment.
4. **Evaluation tooling.** Four layers, all local and offline by default:
   - `pytest` with `--cov=src --cov=tools --cov=evals` and
     `--cov-fail-under=100`, plus `mypy`, `ruff` and `bandit` in
     `pyproject.toml`; CI runs the gate on Ubuntu and Windows.
   - The `evals/` harness (`python -m evals`) runs the metric families over a
     suite and writes `evals/reports/`. Model answers are replayed from
     recordings, so evaluation needs no key and no network.
   - The supplied `tools/evaluate.py` is the format oracle for the scored run.
     It is vendored as supplied, excluded from coverage, and never edited.
   - `reports/scored-run.json` and `reports/scored-run.md` are the published
     run; `tests/test_docs_numbers.py` holds the prose to those files.

## Rejected alternatives

- **FastAPI or Flask for the bank API.** Rejected: the harness is supplied and
  must not be rewritten for the assessment, and adding a framework to a client
  adds a dependency, a server and a CVE surface for no route the pipeline needs.
  The bank API is a fixture, not our product.
- **Postgres for records and reviews.** Rejected: the demo runs on one machine
  with no shared environment, and SQLite is the store the mock already uses.
  Postgres would add an install step to the six-minute fallback and to CI.
- **Deploying the pipeline as a service for the assessment.** Rejected: the
  rubric scores the prepared record, the refusals and the audit trail. A service
  moves the evaluated surface to infrastructure and makes the run depend on
  credentials the assessment does not provide.
- **Docker for the assessed run.** Rejected for the same reason as the service:
  the loopback run is what the demo rehearses and what the fallback needs. The
  image stays for the pilot.
- **A local JSON log as the audit trail.** Rejected: an approval that lives in
  the caller's file system can be edited by the caller. The bank's store owns
  the record, and `src/review_gate.py` re-reads it before a write.

## Consequences

- The gate must prove Windows and Linux parity by hand, because there is no
  framework to absorb path and socket differences. The `pytest-windows` job and
  the COF-49 span-order fix exist for that.
- Provider SDKs stay optional imports (`src/model_clients.py`): the assessed run
  replays recorded answers, and a live run is an opt-in extra.
- The AWS artifacts can drift from the code they describe. The Terraform README
  is the place to say when it was last checked; it currently says it has never
  been applied.
- The mock's SQLite is the single-writer store. One demo run at a time per state
  file, which the loop already enforces with a fresh state file per run.
