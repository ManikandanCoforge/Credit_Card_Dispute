# Roadmap

- Last updated: 2026-10-27
- Current state: 2026-10-27, integrated head `b4e988d` on `kenmann01/cof-40-cof-42-wire-retry-and-review-gate`; the COF-48 docs branch is cut from it
- Related: `docs/LIMITATIONS.md`, `docs/decisions/ADR-001-model-narrative-boundary.md`, `docs/decisions/ADR-002-policy-version-selection.md`, `docs/decisions/ADR-003-hybrid-model-questions.md`

This roadmap starts from what the software does now. It does not describe work that is already complete as future work, and it does not promise a date that has not been agreed.

## Current baseline

At this head the application can:

- read the bank case list and build one working record per complaint
- read the intake, attachment, procedure, policy, and follow-up files by source id
- select the policy version from the Reported date, with inclusive effective windows
- call the `transactions` and `merchant` tools through the local mock with bounded retry: at most three attempts, a doubling backoff with jitter, a per-tool circuit breaker, and a 5 s socket timeout
- assemble the supported classifications (unauthorized, duplicate_charge, service_not_received), route conflicting and unsupported accounts to a person, and include missing-evidence drafts routed to request_information with one targeted question per absent field, with exact citations, a per-type deterministic deadline, and the template narrative
- continue after a case-level failure and report the reason for the case that stopped
- open a human review for each finished draft, create a record only after a person approves the unchanged draft, return the existing record for a duplicate redelivery, and refuse a changed draft
- attempt all twelve dev cases and publish a scored run with per-case pass/fail, p50 and p95 read from the meter file, and measured cost: 11 of 12 in the published report from `dfd90c1`, with CARD-D09 the only exception (`reports/scored-run.md`)
- write one redacted meter line per case and refuse a restricted value in any meter field
- run lint, mypy, Bandit, and pytest with a 100 percent line-coverage gate in CI

CARD-D09's intake adds a delivery note that the parser joins to the customer's account, so the joined statement is not one exact excerpt of the intake and the contract refuses to build it; this is the COF-43 limit recorded at `docs/RED_TEAM.md:52` and enforced at `src/contract.py:1120-1121`.

## Near term

Target: complete the core contract and the create path for the supplied case types. This target is delivered on `b4e988d`. The earlier near-term classification and follow-up items are closed by the integrated head: the scored run passes CARD-D05 (ambiguous) and CARD-D06 (unsupported), and CARD-D05 cites both its intake and its follow-up. The create path is closed by COF-42. The one residual, all twelve cases passing, is on the not-done list below.

Delivered on this head:

| Ticket | Delivered capability | Commits |
|---|---|---|
| COF-40 | Bounded retry and failure routing: at most three attempts, a doubling backoff with jitter, a per-tool circuit breaker, and a 5 s socket timeout; a persistent transaction outage routes the case to `manual_review` with null amount and currency, and a persistent merchant outage stops the case. | `14b1524`, `7ec4df4`, `f1e2bb4`, `653443c` |
| COF-42 | Review gate and record creation: the runner submits each finished draft, a person approves the exact hash in a separate terminal, the runner creates only after approval, a changed draft is refused, a duplicate redelivery returns the existing record, and no module under `src/` can run the operator command. | `ef47e16`, `011a147`, `e44418c` |
| COF-43 | Per-case meters: one redacted meter line per case, a restricted-value refusal, p50 and p95 read from the meter file, and the published report. | `022e74f`, `d1b4656`, `e082e91`, `3d62534`, `1a995f7` |

## Not done

These items are not delivered on this head.

- decide which of two contradictory accounts is true; the application routes the case to `manual_review` instead
- authenticate a reviewer or run batch intake
- turn on the optional model route: `ADR-003` lets a qualified model answer two closed questions on the classification gap, and it is off by default with no approved live run
- update or close an existing record; this is blocked by Gate U
- provide a UI or a production deployment
- pass all twelve dev cases: CARD-D09 remains the only exception, proposed and pending pod agreement (COF-43)
- enforce the review rules through GitHub rulesets (issue #6); this is blocked on the private repository's plan, and the existing checks ruleset has enforcement disabled

## Sequencing gate: update and close

**Gate U is the first mid-term decision. It is not a feature and it cannot be skipped.**

Update and close of existing cases must sit behind a separately agreed contract. No update or close code, schema, endpoint, or UI work may start before that contract is signed.

The separate contract must define at least:

- allowed states and transitions for a case record
- who may request an update or close, and who may approve it
- how approval is re-bound when a draft changes, and whether a new review is required
- idempotency and conflict rules for update, distinct from create
- audit events, retention, and the evidence kept for each transition
- concurrency, duplicate delivery, and rollback behaviour
- test fixtures and acceptance cases for update and close

The current mock supports create only. An unsupported POST path returns `404 unsupported_operation` and is audited; other HTTP methods are not handled, and update or close do not exist. The gate is therefore enforced in the simulator as well as in this document.

After Gate U, the mid-term order is auth and identity, batch intake, the model narrative route after approval, and richer evaluation. Update and close implementation follows auth, because an update needs a verified approver. It is listed as a later item, not as an assumed capability.

## Mid term

Entry condition: the near-term core is delivered and the create path is demonstrated. These items are larger than a single ticket and need client agreement where noted.

| ID | Item | Current gap | Done when |
|---|---|---|---|
| M1 | Authentication and reviewer identity | The mock has no login, session, role, or verified reviewer. The operator CLI accepts a free-text name. | A reviewer signs in through an approved identity provider. Roles separate the requester from the approver. The server checks authorization, and the audit binds the decision to a verified identity, not a typed name. |
| M2 | Batch intake | One case is processed at a time. There is no queue, rate limit, or backpressure. | A bounded batch can be submitted. Each case is isolated, partial failures are reported per case, retries do not duplicate a record, and the audit keeps the batch and case relationship. |
| M3 | Model narrative route, after client approval | No narrative model is configured. The shipped narrative is the deterministic template. The hybrid's model questions (`ADR-003`) do not write prose. | The client has approved the provider, data boundary, and spend. The route follows `ADR-001`: deterministic fields are frozen first, the model writes prose only, citations are unchanged, output is validated, and the template remains the fallback. Latency and cost are measured, not estimated. |
| M4 | Richer evaluation | The evaluator checks exact substrings. It does not establish semantic support, and the semantic rubric is not written. | A held-out set covers normal, ambiguous, unsupported, outage, duplicate, stale-policy, and prompt-injection cases. Citation support is reviewed against a written rubric. Redaction, approval binding, and duplicate prevention are regression-tested. The scoreboard is repeatable. |

## Later

Entry condition: a pilot or a new client agreement. These items are not part of the current capstone delivery.

| ID | Item | Current gap | Done when |
|---|---|---|---|
| L1 | Update and close of existing cases | Not implemented. Blocked by Gate U. | The Gate U contract is signed, auth is live, and update and close follow the agreed state machine, approval, idempotency, and audit rules. |
| L2 | Production deployment and operations | Only a dev container and a local `serve` command exist. There is no orchestration, metrics, tracing, or alerting. | A reproducible deployment runs in an approved environment, with health checks, redacted structured logs, metrics, alerting, backup, and a recovery runbook. |
| L3 | Immutable audit and retention | Audit is a local SQLite table in a mutable file. | Audit events are written to an append-only store with retention, access control, and export for review. The local table is not described as immutable. |
| L4 | Analyst UI | Output is JSON and CLI text. | A reviewer can open a case, see facts, citations, missing evidence, and the draft, and approve or reject with a visible hash. The UI does not bypass the server-side boundary. |
| L5 | Policy lifecycle tooling | Policy versions are Markdown files with effective windows. There is no authoring, validation, or publication workflow. | A new version can be authored and validated against the window and procedure rules, published with an audit record, and selected historically without changing old drafts. |
| L6 | Real integrations and multi-currency | Payment, merchant, and customer systems are fixtures. All amounts are `XCR`. | An approved adapter boundary exists for the bank's systems, with authentication, timeouts, retry policy, and currency handling defined and tested. This requires a new scope agreement. |

## Explicitly out of scope until renegotiated

These are not roadmap commitments:

- adjudication, refunds, reimbursement, or any customer outcome promise
- production identity in the current mock
- OCR, model fine-tuning, or complex entity resolution
- real payment, card-network, or merchant APIs
- a polished production UI
- update or close before Gate U

## How roadmap items are accepted

Each item is accepted only when:

1. The mapped evaluator case or a new regression case passes, not just a unit test.
2. CI is green, including lint, Bandit, pytest, and the coverage gate.
3. One reviewer has approved the change.
4. Any new log line has been checked for restricted values.
5. The limitation it addresses is updated in `docs/LIMITATIONS.md`.

Items that change the model boundary, policy selection, or case lifecycle also require an ADR update or a new ADR before implementation.
