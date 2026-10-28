# Security

The project is a training simulation for a bank dispute copilot. It never holds real
customer data and it is not a production dispute system, but it does handle restricted
values, instruction-shaped evidence and a reviewer decision, so a defect in that path is
worth a private report.

## Reporting a vulnerability

Report a suspected vulnerability privately:

- GitHub's Security tab on this repository, then "Report a vulnerability". That opens a
  private advisory that only the maintainers can read.
- Or the pod's own channel if you are in the pod.

Do not open a public issue for a suspected vulnerability, and do not include a live key,
a card number or a customer name in the report. A short reproduction, the affected path,
and what an attacker gains is enough to start.

## In scope

- The copilot code in `src/`: the contract rules, untrusted evidence handling, escalation,
  resilience, meters, review gate and runner, span store and observability.
- The runtime and the evaluation tooling in `tools/`, and the checks workflow in
  `.github/workflows/`.
- The supplied mock bank in `evals/mockbank.py`, where a defect lets a caller read or write
  state it should not, or forge or hide an audit row. The audit is the record of what the
  application asked for, so its integrity is part of the boundary.

## Out of scope

- The synthetic fixtures under `evals/fixtures/` and the test data under `tests/`. Every
  institution, person, policy and amount in them is fictional by design. A report that a
  fixture looks like real data is still welcome, and it is handled as a data handling
  question rather than as an exploit.
- Real customer data. The project never holds any, and no path in it accepts a real
  account number or complaint.
- The operator command's simulated reviewer identity. It takes a reviewer name as free
  text, with no login, session or role check. Anyone who can reach the mock on the local
  machine can act as a reviewer; that is the documented training boundary, not a
  vulnerability.
- The supplied grader `tools/evaluate.py` and the package validator
  `tools/validate_package.py`. They are supplied and hash-checked, so a defect there goes
  to the pod, not to a patch in this repository.
- A denial of service against your own loopback process, and misconfiguration of a local
  machine that the rules below already cover.

## The local-only binding rule

The mock binds loopback, `127.0.0.1`, and stores its state in a local SQLite file. Keep it
there:

- Do not expose the mock or the state file to a network, a shared drive or a container port.
- Keep the operator command in a separate terminal on the same machine.
- One isolated copy and one state database per team, because the state file is not built
  for two writers.
- A change to a bind address or to the reachable surface is a security change: it needs a
  review from the owner of the affected module before it merges.

## Secrets

Credentials come only from the environment. `MODEL_PROVIDER` selects the model, and a live
client reads `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY`, or
`ANTHROPIC_FOUNDRY_RESOURCE` and `ANTHROPIC_FOUNDRY_API_KEY`. The rules that follow from
that:

- No provider key, token or endpoint secret in the repository: not in `models.toml`, not in
  a fixture, not in a test, not in a report.
- `.env` is git-ignored and is the only place a local key belongs. The `env-files` job in
  `.github/workflows/checks.yml` rejects a committed `.env` or `.venv/`.
- Error messages name a setting, never its value, and a credential is never written to a
  log, a span or an audit row.
- CI has no secrets and runs with `permissions: contents: read`.
