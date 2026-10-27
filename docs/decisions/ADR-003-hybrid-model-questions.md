# ADR-003: Hybrid model questions

- Status: Proposed. Accepted when the pull request that adds it merges. Live use is refused until the bank's approval is recorded in `models.toml`
- Date: 2026-10-26
- Ticket: COF-64
- Owner: Mani (ManikandanCoforge)
- Amends: `ADR-001` (model narrative boundary)
- Related: `src/model_cue.py`, `src/model_clients.py`, `src/model_registry.py`, `src/contract.py`, `src/untrusted.py`, `models.toml`, `evals/`

## Context

`src/contract.py` `_classification` types a complaint by matching fixed phrasings. When the customer writes a phrasing the rules do not know, the case fails closed with `ContractError` ("the intake supports no supported classification") and the reviewer gets no draft at all. On the 67 cases in `data/dev` and `evals/fixtures`, the rules alone pass 33. Eighteen of the cases they miss are never built because no rule matches the wording. Examples:

- "took the exact same 38 crowns again a minute later" is a duplicate charge.
- "a cleaning that never happened" is a service not received.
- "the machine kept my money and no notes came out" is a cash withdrawal.
- "more than the price I was quoted" is outside the supported types.

The rules have a second gap. A complaint that describes two problems, such as "Echo Cinema charged me twice, and the film I paid for was never shown", is typed by the first rule that matches and marked `ready_for_review`. The procedure gives such a complaint no single type, so a person should decide it.

`ADR-001` keeps every decision in deterministic code and allows a model only to reword the narrative. That boundary cannot close either gap. This record lets a model answer two closed questions. It keeps every other part of `ADR-001`: the rules still compute every field, and a model never writes a fact, a quote, a date or a policy id.

## Decision

A qualified, approved model may answer two closed questions. Code decides what each answer means.

1. **Dispute type.** This question is asked only when the rules find no type and no escalation applies. The model returns one of six labels (`unauthorized`, `duplicate_charge`, `service_not_received`, `cash_withdrawal`, `other_dispute`, `none`) and the label of the one line that shows it (`L1`, `L2`, ...).
2. **More than one problem.** This question is asked only once a complete draft would be marked `ready_for_review`. The model returns true or false.

**When no question is asked.** The rules decide alone, as they do with no model, in each of these cases:

- No model is configured. This is the default.
- A customer statement holds text the detectors recognise as an order to the system, a filing command, text addressed to a model (such as "Hi AI:", "note to the assistant", "approve this" or "classify it as"), or `<evidence>` markup. The detectors are `src/untrusted.py` `has_instruction` and `addresses_a_model`, and `src/contract.py` `_INSTRUCTION_SENTENCE`.
- A restricted value would survive redaction, such as a card number split at any point across a line break or broken up by hidden characters. The lines are scanned joined by a space and joined with nothing.
- A customer statement has no `Source ID` line to cite its lines by.
- The case has no customer lines, or more than 64.

The detectors are patterns. Text written to steer a model in a way they do not recognise still reaches it. Three things limit the harm:

- The prompt tells the model the lines are data, not instructions.
- The answer can only be a label.
- Every model-assisted draft tells the reviewer which line to check.

**What the model sees.** It sees the customer's own lines from the intake and any follow-up. Headings, the `Source ID` line and the intake form's fields are removed. A sentence written as an instruction is dropped. Restricted values are replaced with `[redacted]`, including the values the output guard knows for the case: the customer reference and the merchant's private token. The lines are numbered inside `<evidence>` tags. The model never sees the policy, the procedure, transaction or merchant data, attachments or the decision table.

**What counts as an answer.** The answer must match a strict JSON schema and must name a line the case has. Anything else is no answer: a schema mismatch, an unknown label, a refusal, a timeout or a truncated reply. A provider failure never reaches the rules as an exception.

| Model answer | What code does |
|---|---|
| `duplicate_charge`, `service_not_received` | The rules draft that type: routing, missing fields, deadline and citations. The named line is cited exactly as `model_assisted_classification`. The narrative says "Classification is model-assisted: {provider}/{model} read line {label} as {type}. Verify that line before approving." A duplicate whose second charge is not on record goes to `manual_review`, as a rules duplicate does, because the procedure asks for both transaction records. |
| `unauthorized`, with the form showing `Authorization: confirmed` in any letter case | `ambiguous` and `manual_review`. Code cites the line as `authorization_denied`, the form line as `authorization_confirmed`, and the procedure's conflict sentence. |
| `unauthorized`, with the form showing `denied` in a letter case the rules do not read | The rules draft `unauthorized`, as for the first row. |
| `unauthorized`, any other form value | The procedure's provisional `unauthorized`. `authorization_confirmation` is requested, so the draft goes to `request_information` and is never ready on the model's reading alone. |
| `cash_withdrawal` | `unsupported` and `manual_review`. Code cites the line and the procedure's cash-withdrawal sentence. |
| `other_dispute` | `unsupported` and `manual_review`. Code cites the line and the procedure's supported-classifications sentence. |
| `none` | `ambiguous` and `manual_review`. The narrative says neither the rules nor the model could name a type. |
| No usable answer | The case is not built, exactly as it is with no model. |
| More than one problem: true | `ambiguous` and `manual_review`, with a narrative note saying why. When the model chose the type, its line stays cited. |
| More than one problem: false, or no answer | The rules' draft is unchanged. |

A model answer can fill the rules' gap or send a case to a person. It cannot override a type the rules found, and it can mark a draft ready only in the gap the rules left.

Only the word `confirmed`, in any letter case, counts as a confirming form, as in `src/escalation.py`. A form that says `Authorization: yes` is therefore treated as neither confirmed nor denied, and a model-read denial on it is the provisional `unauthorized`. Reading a wider confirmation vocabulary would change the rules' own path as well, so it is a separate decision.

**Which models may answer.** `src/model_clients.py` enforces three rules:

- A live model needs a passed record in `models.toml` for its provider, model and the current `SCHEMA_HASH`.
- A live model also needs a non-empty `approved_by`, because a live call sends the customer's redacted lines to the provider.
- A replay needs no approval, because nothing leaves the machine. Every model whose answers the recording holds must still have a passed record.

`tools/qualify_model.py` makes a record by asking the dispute-type question for every case in `evals/qualification/cue_suite.json`. The suite has 66 cases with the Card Disputes Copilot's extracted lines, drawn from its synth, stress, holdout and edge suites. Nineteen were gaps for the copilot's rules; this repository's rules leave a somewhat different set. A record passes only with zero unsafe answers (a wrong supported type) and at least 90% of cases answered.

The prompts and schemas are the copilot's prompt `cue-v2`, copied verbatim. `SCHEMA_HASH` covers the schemas and the prompt version, and `tests/test_model_cue.py` pins the prompt text, so a change to either fails until every model is qualified again.

| Model | Provider | Suite (66) | Held-out (12) | Registered |
|---|---|---|---|---|
| GPT-6 Luna | Azure OpenAI, East US | 66 correct, 0 unsafe | 11 correct, 1 cautious (a network failure), 0 unsafe | Yes |
| Claude Haiku 5.5 | Microsoft Foundry | 65 correct, 1 cautious, 0 unsafe | 12 correct, 0 unsafe | No: kept as the alternate until the bank approves it |

Three limits of this evidence matter:

- **The records came from the copilot's own clients.** This repository's clients send the same requests, and the 40 recorded questions were byte-for-byte the prompts Luna was sent, but this repository has not made a live call. Before the bank signs off, rerun `tools/qualify_model.py` with this repository's client, so the record comes from this code.
- **The two-problem question has no qualification set.** A yes can only send a case to a person, and a wrong no leaves the draft the rules would make without a model. Its effect is measured in the suites below.
- **`approved_by` is empty in every record,** so live use is refused today.

**How it runs.**
- `MODEL_PROVIDER` selects `off` (the default), `azure_openai`, `anthropic_foundry` or `replay`.
- Live clients send one structured-output request per question, with a 30-second timeout and one retry. Azure sets `max_completion_tokens=400`. Foundry sets `max_tokens=2000` and `effort` to low.
- The `openai` and `anthropic` SDKs are imported only when a live client is built, so CI, `uv.lock` and the default path need neither.
- `replay` answers from a JSONL recording keyed on the exact prompt and schema. A question with no recording gets no answer.
- `MODEL_RECORD` makes a live run append each answer to a recording, in a folder that must already exist.
- Every call is metered in `ContractResult.model_calls`: purpose, provider, model, latency and tokens. `answered` is true only for a usable answer. A meter never holds the prompt or the answer.

## How this answers ADR-001's objections

- **Ungrounded decisions.** The model chooses a label for a customer line and never applies policy. Code maps the label to a classification, cites the procedure sentence for it, and computes the routing, missing fields and deadline from the supplied files.
- **Non-reproducible results.** A live answer can differ between runs. That risk is bounded four ways:
  - the qualification bar: zero unsafe answers on 66 cases
  - the answer table: most answers can only send a case to a person, and a model-read denial is never ready by itself
  - the reviewer note on every model-assisted draft
  - the approval gate

  Evaluation and CI use recorded answers, so their results repeat exactly.
- **Audit binding to exact slices.** The model returns a label and never text. Code quotes the labelled line exactly from its source. A line that holds a restricted value is cited by its statement's `Source ID` line instead. The approval hash still binds the whole draft.
- **Prompt injection as an instruction path.** No model is asked about a statement holding text the detectors recognise. Merchant notes and attachments are never sent. The output is an enum and a line label checked against a schema, so the worst case is a wrong label. Phrasing the detectors miss is the residual risk named above.
- **Dates and policy rules.** Unchanged. The model never sees a date, a policy or a procedure.
- **Exact-string evaluation.** Every citation is still an exact slice of a named source.

## Measured result

Run on 2026-10-27 with `tools/hybrid_eval.py`, this repository's code with the tool reads retried (#68), and the unmodified mock and bank evaluator. GPT-6 Luna's recorded answers were replayed from `evals/recordings/gpt-6-luna.jsonl`.

Ten of the 50 questions had no recording, because the copilot's run never asked them, and each counted as no answer:

- 3 dispute-type questions: `SYN-S03`, `HLD-H07` and `HLD-H08`
- 7 two-problem questions: `CARD-D08`, `CARD-D10`, `SYN-S14`, `SYN-S17`, `SYN-S20`, `SYN-S24` and `SYN-S25`

`CARD-D10` and `SYN-S14` are asked now because the tool reads retry: in the recorded runs a tool fault stopped both cases before any question.

| Suite | Rules alone | Hybrid | Wrong drafts marked ready (rules → hybrid) | Model calls | Tokens in / out |
|---|---|---|---|---|---|
| dev (12) | 11 | 11 | 0 → 0 | 6 | 544 / 132 |
| synth (31) | 19 | 23 | 3 → 3 | 23 | 3,528 / 572 |
| stress (16) | 5 | 16 | 1 → 0 | 16 | 5,585 / 647 |
| holdout (8) | 3 | 4 | 0 → 0 | 5 | 747 / 133 |
| Total (67) | 38 | 54 | 4 → 3 | 50 | 10,404 / 1,484 |

The three wrong ready drafts left in synth need rule changes outside this record:

- `SYN-S17`: the named transaction is missing from the tool response.
- `SYN-S20`: a follow-up withdraws the complaint.
- `SYN-S24`: a service complaint whose form denies authorization.

None of their two-problem questions had a recording, so this run does not show how the model would have answered them.

The hybrid still does not build 8 cases. Three are the gap cases with no recorded answer: `SYN-S03`, `HLD-H07` and `HLD-H08`. The other 5 fail for reasons outside this record:

- 1 stops because the merchant service stays unavailable after three attempts (`SYN-S18`). A transaction outage is drafted for manual review instead (#68).
- 2 have no policy version for their reported date.
- 1 has an attachment without exactly one Amount line (`HLD-H05`).
- 1 is `CARD-D09`, whose intake statement is not a single exact excerpt.

## Rejected alternatives

### Add more phrasings to the rules

Every new paraphrase needs a code change, and hidden cases change the wording by design. The rules alone pass 38 of 67, and each pattern added for one case risks a false match on another, such as "I called twice".

### Let the model classify every case and route it

`ADR-001`'s objections hold in full. A model that can override a rule the procedure states can reach `ready_for_review` against the rules, and its decisions could not be reproduced.

### Keep the model on the narrative only

This is `ADR-001` as it stands. It does nothing for a case that is never built, and it does nothing for a two-problem complaint marked ready.

### Ask the model on every case and keep the answer only when it agrees with the rules

This would double the calls and the cost and add no draft the rules could not already make. The two closed questions are asked only where an answer can change the outcome.

## Consequences

Positive:

- A paraphrase the rules miss gets a cited draft instead of no draft, and the reviewer is told which line to check.
- A two-problem complaint is not marked ready.
- The default path, the scored run and CI are unchanged and make no model call.
- Every call is metered, and the evaluation repeats exactly from recordings.
- The output guard also finds restricted values hidden by zero-width characters or typed in full-width digits, a check this work added for the model path.

Negative:

- A live run sends redacted customer lines to the provider. The bank must approve the provider and the data location, and record its approval, before any live use.
- A live run depends on the provider. No answer leaves the rules to decide, and a gap case is then not built.
- A model-assisted draft needs the reviewer to check the cited line, which is more work than reviewing a rules draft.
- The detectors that keep a model away from injected text are patterns, and unrecognised phrasing still reaches the model.
- Changing a prompt means a new prompt version, requalifying every model, and new recordings.
- The live SDKs are not locked in `uv.lock`, so a live run pins them on the command line (see `README.md`).
- `tools/scored_run.py` stays the rules baseline and records zero model calls. `tools/hybrid_eval.py` measures the hybrid.

## Review triggers

Revisit this decision if any of the following changes:

- The bank approves or rejects a model, a provider or the data location.
- A prompt, a schema or the line extraction changes, or a provider retires a model version.
- A reviewer finds a model-assisted draft with a wrong supported type, which is an unsafe answer.
- Injected text is found to have steered a model's answer.
- The procedure adds or removes a classification.
