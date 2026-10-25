# ADR-001: Model narrative boundary

- Status: Accepted
- Date: 2026-10-25
- Ticket: COF-47
- Owner: Ken (kenmann01)
- Related: `BRIEF.md`, `docs/OUTPUT_CONTRACT.md`, `docs/ASSESSMENT.md`

## Context

The draft given to a human reviewer needs readable prose: what the customer says, what the evidence shows, what is missing, and what the reviewer should do next. The brief permits a model where it helps and asks the team to explain where deterministic code is preferable. The supplied procedure requires human approval of the exact draft, and the brief and output contract require citations to be exact excerpts.

A model is useful for prose. It is not a reliable source of classification, routing, policy selection, date arithmetic, or provenance. This record fixes that boundary before any model route is enabled.

## Decision

A model, if used, may write narrative prose only. Classification, routing, policy selection, deadline arithmetic, citations, approval and record creation stay deterministic code.

The narrative is a presentation layer over facts that deterministic code has already fixed. A model may rephrase the summary and the customer-facing message. It may not:

- add, remove, or change a fact, citation, policy id, deadline, or missing-information field
- choose or change the classification or routing
- choose or change the policy version or procedure
- calculate or repair a deadline
- create, edit, or paraphrase a quotation
- decide an approval or call the record-creation endpoint
- promise a refund, outcome, reimbursement, or eligibility

Every narrative remains a draft for human review and is labelled as a draft.

## Deterministic surfaces

| Surface | Deterministic owner | Current anchor | Model may write? |
|---|---|---|---|
| Classification | Rules code | `src/contract.py` `_classification` | No |
| Routing | Assembly code | `src/contract.py` `assemble_contract` | No |
| Policy version and procedure | Selection code | `src/build_records.py` `_policy` and `_policy_versions` | No |
| Deadline | Date arithmetic | `src/contract.py` `_deadline` | No |
| Citations | Exact source slices | `src/contract.py` `_statement`, `_unique_line`, `_sentence`, `_transaction_citation` | No |
| Missing information and questions | Rules code | `src/build_records.py` `_missing_information`; contract assembly | No |
| Approval | Mock review service and operator CLI | `POST /v1/reviews`, draft hash, `tools/runtime.py` | No |
| Record creation | Service code and idempotency | `POST /v1/records`, `Idempotency-Key`, duplicate check | No |
| Narrative | Deterministic template now; optional model later | `src/contract.py` `_narrative` | Prose only |

## Rejected alternative

Let the model decide classification and routing, and let it generate the citations, with deterministic code only performing the final record write.

## Why the alternative was rejected

- **Ungrounded decisions.** The model would infer from ordinary meaning rather than the supplied policy and procedure. Hidden cases combine missing evidence, conflicts, outages, and hostile attachments. A plausible answer is not the same as a rule-bound answer.
- **Non-reproducible results.** Sampling, provider changes, model upgrades, and prompt edits can change the classification, route, deadline, or citation set for the same evidence. The same input must produce the same contract so that a reviewer, an auditor, or a rerun can compare drafts.
- **The audit cannot bind to exact source slices.** The approval hash binds the reviewer to the canonical JSON of the draft, but a model-generated quote has no deterministic position in a source document. A reviewer could not prove which words supported which claim, and a changed draft could not be traced back to a source slice. Deterministic extraction fails closed with `ContractError` when an exact slice cannot be made.
- **Prompt injection becomes an instruction path.** Merchant notes and attachments are untrusted data. Deterministic code quotes them as evidence. A model that follows text inside them could change a route or a claim, which is a critical failure in the assessment.
- **Dates and policy rules are fixed.** Deadline arithmetic must be checkable against the selected policy version. Model arithmetic or model-selected policy versions cannot be accepted, even when the prose reads well.
- **The evaluator checks exact strings.** `tools/evaluate.py` validates citations by exact substring and validates policy ids against the expected set. A generated quote may pass by coincidence or fail without warning; neither outcome demonstrates grounding.

## Current shipped path

The shipped path is the deterministic template.

`assemble_contract` calls `_narrative`, which returns a fixed template sentence containing the case id, classification, routing, deadline, and the fact that no case has been created. A second template sentence names the outstanding fields when evidence is missing. There is no model client, model credential, prompt, model network call, or sampling step in this repository. `README.md` states that the package has no LLM account or model credits.

The model route is optional and gated on client approval. It does not ship by default. The pod plan records the model approval as the riskiest unknown and requires an answer before the template path is replaced. If the client does not approve the route, the template remains the narrative.

If the route is approved later, it must be implemented behind this boundary:

1. Compute and freeze every deterministic field first.
2. Pass only the already-selected evidence text to the model.
3. Treat model output as untrusted input, not as a contract field.
4. Reject output that introduces a fact, source id, citation, date, amount, policy id, missing field, or outcome promise.
5. Keep every citation unchanged and separately verified as an exact slice.
6. Label the result as a draft and keep the template as the fallback for model errors, timeouts, or validation failures.
7. Record the model identifier, prompt version, and validation result before the route is enabled.

None of those steps is claimed as implemented today.

## Consequences

Positive:

- Decisions are replayable and testable from the supplied sources.
- The approval hash has a stable meaning: it binds a draft whose evidence fields can be re-derived.
- A reviewer can check every quote against its named source.
- The template path has no external dependency and always produces a draft.

Negative:

- The template is terse and not tailored to the customer. It is less fluent than a model-written narrative.
- A future model route adds latency, cost, and validation work. Those numbers must be measured before any claim is made.
- The team must maintain both the template and the model adapter, and keep the template as a real fallback rather than a dead path.

## Review triggers

Revisit this decision if any of the following changes:

- The client approves a model route and names the approved provider and data boundary.
- A requirement appears for customer-facing prose beyond the current draft sentence.
- The output contract adds fields that a model might be asked to populate.
- A hidden or production case shows that the deterministic citation set is too narrow for the evidence.
