# Roadmap

- Last updated: 2026-10-25
- Current state: 2026-10-25, branch `kenmann01/cof-47-decision-record-limitations-and-roadmap`, with COF-38 missing-evidence routing and the COF-44 scored run included
- Related: `docs/LIMITATIONS.md`, `docs/decisions/ADR-001-model-narrative-boundary.md`, `docs/decisions/ADR-002-policy-version-selection.md`, `docs/decisions/ADR-003-hybrid-model-questions.md`

This roadmap starts from what the software does now. It does not describe work that is already complete as future work, and it does not promise a date that has not been agreed.

## Current baseline

At this head the application can:

- read the bank case list and build one working record per complaint
- read the intake, attachment, procedure, and policy files by source id
- select the policy version from the Reported date, with inclusive effective windows
- call the `transactions` and `merchant` tools through the local mock, with one observed read per tool
- assemble a contract for the supported classifications (unauthorized, duplicate_charge, service_not_received), including missing-evidence drafts routed to request_information with one targeted question per absent field, with exact citations, a per-type deterministic deadline, and the template narrative
- continue after a case-level failure and report the reason for the case that stopped
- attempt all twelve dev cases and publish a scored run with per-case pass/fail, the exact failed check, p95 template latency and measured cost (`reports/scored-run.md`; 7 of 12 on 2026-10-25, five proposed exceptions)
- run lint, mypy, Bandit, and pytest with a 100 percent line-coverage gate in CI

It does not yet:

- classify `ambiguous` or `unsupported`, or resolve conflicting accounts
- assemble conflicting cases, follow-up documents, or tool-fault cases
- authenticate a reviewer or run batch intake
- call a model unless one is configured: `ADR-003` lets a qualified model answer two closed questions on the classification gap, and it is off by default
- provide a UI or a production deployment

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

## Near term

Target: complete the core contract and the create path for the supplied case types. These are prerequisites for a credible end-to-end demo.

| ID | Item | Current gap | Done when |
|---|---|---|---|
| N1 | Complete classification, routing, and null deadlines | Missing-evidence routing and the three supported classifications are in place (COF-38). `ambiguous`, `unsupported`, and conflicting accounts still raise on this branch; PR #52 (COF-39) adds them and is in review. | `duplicate_charge`, `service_not_received`, `ambiguous`, and `unsupported` follow `CARD-PROCEDURE-01`. Routing precedence is applied. Unsupported and ambiguous cases have a null deadline. Every supplied dev case produces the expected classification, routing, missing fields, and deadline. |
| N2 | Read every case-named evidence source | `src/contract_records.py` refuses a document outside the intake and attachment pair, so `CARD-D05` stops on its follow-up. PR #52 reads follow-ups for escalation and PR #53 (COF-41) treats their content as untrusted evidence; neither is merged on this branch. | Every source named by the case list is read into evidence, including follow-up documents. A source outside the supported evidence types is refused with a reason, never silently dropped. Conflict cases cite both contradictory sources and route to `manual_review`. |
| N3 | Bounded retry and failure routing | In place: `src/contract_records.py` retries a transient read through `src/resilience.py` (at most three attempts, doubling backoff, a per-tool breaker), routes a persistent transaction outage to `manual_review` with null facts, and stops a case whose merchant read stays unavailable. | A transient failure is retried within the procedure limit of three total attempts. A persistent failure stops, routes to `manual_review`, and leaves amount and currency null. No failed read is treated as an empty history. |
| N4 | Approval and record creation from the runner | In place: `src/review_runner.py` submits the exact draft, waits for the human decision, and creates only after approval; a changed draft is refused and no module under `src/` can run the operator command. | The runner submits the exact draft, waits for a human decision, and creates only after approval. A changed draft is rejected. `Idempotency-Key` replay returns the original record. A duplicate underlying complaint returns the existing record and creates nothing. The audit shows the review hash and the creation event. |
| N5 | Evaluation across the supplied set | The scored run publishes all twelve case results, but 7 of 12 are emitted and the five exceptions are proposed, not agreed. Narrative grounding is a human check. | All 12 dev cases pass, the exception list is empty and agreed, and the report is reproducible from a clean checkout. Citation exactness, policy ids, facts, deadlines, missing fields, questions, restricted values, and narrative presence are reviewed. |

## Mid term

Entry condition: the near-term core is green and the create path is demonstrated. These items are larger than a single ticket and need client agreement where noted.

| ID | Item | Current gap | Done when |
|---|---|---|---|
| M1 | Authentication and reviewer identity | The mock has no login, session, role, or verified reviewer. The operator CLI accepts a free-text name. | A reviewer signs in through an approved identity provider. Roles separate the requester from the approver. The server checks authorization, and the audit binds the decision to a verified identity, not a typed name. |
| M2 | Batch intake | One case is processed at a time. There is no queue, rate limit, or backpressure. | A bounded batch can be submitted. Each case is isolated, partial failures are reported per case, retries do not duplicate a record, and the audit keeps the batch and case relationship. |
| M3 | Model narrative route, after client approval | No narrative model is configured. The shipped narrative is the deterministic template. The hybrid's model questions (`ADR-003`) do not write prose. | The client has approved the provider, data boundary, and spend. The route follows `ADR-001`: deterministic fields are frozen first, the model writes prose only, citations are unchanged, output is validated, and the template remains the fallback. Latency and cost are measured, not estimated. |
| M4 | Richer evaluation | The evaluator checks exact substrings. It does not establish semantic support, and it has no held-out set. | A held-out set covers normal, ambiguous, unsupported, outage, duplicate, stale-policy, and prompt-injection cases. Citation support is reviewed against a written rubric. Redaction, approval binding, and duplicate prevention are regression-tested. The scoreboard is repeatable. |

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
