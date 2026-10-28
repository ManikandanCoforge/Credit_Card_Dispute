# ADR-003: Hybrid model questions

- Status: Accepted. On by default since COF-39: GPT-6 Luna's use is approved in `models.toml` as the team's capstone approval (Mani, 2026-10-28). Lumen Bank is fictional, so this is not a bank sign-off; a real bank records its own approval there. Without the model's key, endpoint or SDK, the drafting commands fall back to the rules alone.
- Date: 2026-10-26
- Ticket: COF-64
- Owner: Mani (ManikandanCoforge)
- Amends: `ADR-001` (model narrative boundary)
- Related: `src/model_cue.py`, `src/model_clients.py`, `src/model_registry.py`, `src/contract.py`, `src/untrusted.py`, `models.toml`, `evals/`

## Context

`src/contract.py` `_classification` types a complaint by matching fixed phrasings. When the customer writes a phrasing the rules do not know, the case failed closed with `ContractError` ("the intake supports no supported classification") and the reviewer got no draft at all. Since COF-39 such a case is drafted for manual review as `ambiguous` instead, so it stays in the submission, but it still reaches the reviewer untyped. On the 67 cases in `data/dev` and `evals/fixtures`, the rules alone pass 33. Eighteen of the cases they miss are never built because no rule matches the wording. Examples:

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
| No usable answer | `ambiguous` and `manual_review`, as with no model (COF-39). The narrative says neither the rules nor the model could name a type. |
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

- **The records came from the copilot's own clients.** This repository's clients send the same requests, and the 40 recorded questions were byte-for-byte the prompts Luna was sent, but this repository has not made a live call. Before a real bank signs off, rerun `tools/qualify_model.py` with this repository's client, so the record comes from this code.
- **The two-problem question has no qualification set.** A yes can only send a case to a person, and a wrong no leaves the draft the rules would make without a model. Its effect is measured in the suites below.
- **The approval is the team's, for the capstone.** `approved_by` on GPT-6 Luna's record names Mani (ManikandanCoforge), 2026-10-28. It is not a bank's sign-off on the provider and data location.

**How it runs.**
- `MODEL_PROVIDER` selects `off`, `azure_openai`, `anthropic_foundry` or `replay`. Unset, the drafting commands use the approved default pair, GPT-6 Luna on Azure OpenAI (`src/model_clients.py` `model_or_rules`); a model that cannot be set up makes them draft with the rules alone and say why, never stop.
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

Run on 2026-10-28 UTC with `tools/hybrid_eval.py`, this repository's code with the tool reads retried (COF-40), CARD-D09's statement read from before the form fields (COF-43), a withdrawn complaint or a taken-back denial read as the customer meant it (COF-39), a complaint no rule can type, a merchant outage, a tool 404, a missing named transaction or a date no policy version covers drafted instead of dropped (COF-39), and the unmodified mock and bank evaluator. COF-39 adds no phrase rule. GPT-6 Luna's recorded answers were replayed from `evals/recordings/gpt-6-luna.jsonl`.

Ten of the 51 questions had no recording, because the copilot's run never asked them, and each counted as no answer.

`CARD-D10` and `SYN-S14` are asked because the tool reads retry: in the recorded runs a tool fault stopped both cases before any question. Cases COF-39 now drafts instead of dropping, or sends to a person before a draft would be ready, change which questions are asked. The replay report gives the calls and answers per suite.

| Suite | Rules alone | Hybrid | Wrong drafts marked ready (rules → hybrid) | Model calls | Tokens in / out |
|---|---|---|---|---|---|
| dev (12) | 12 | 12 | 0 → 0 | 7 | 705 / 174 |
| synth (31) | 25 | 29 | 0 → 0 | 21 | 3,528 / 572 |
| stress (16) | 7 | 16 | 1 → 0 | 16 | 5,585 / 647 |
| holdout (8) | 6 | 7 | 0 → 0 | 7 | 747 / 133 |
| Total (67) | 50 | 64 | 1 → 0 | 51 | 10,565 / 1,526 |

The rules leave one wrong ready draft, `STR-P15`: "charged me twice, and the film was never shown" reads as a duplicate because "never shown" is not a service phrase. The model's two-problem answer sends it to a person, so the hybrid has none. Every case is built.

Three cases fail in the hybrid:

- `SYN-S03` and `HLD-H08`: gap cases whose dispute-type question has no recording, so they are drafted for manual review as `ambiguous`, as with no model.
- `SYN-S26`: an instruction in the complaint text that names a type. The case goes to a person where the gold expects the denied form to decide it, which is the team's choice for instruction text.

The gap between the two columns is wording the rules do not read. That is the part this ADR gives to the model, rather than to more phrase rules.

## Rejected alternatives

### Add more phrasings to the rules

Every new paraphrase needs a code change, and hidden cases change the wording by design. The rules alone pass 50 of 67, and each pattern added for one case risks a false match on another, such as "I called twice".

### Let the model classify every case and route it

`ADR-001`'s objections hold in full. A model that can override a rule the procedure states can reach `ready_for_review` against the rules, and its decisions could not be reproduced.

### Keep the model on the narrative only

This is `ADR-001` as it stands. It does nothing for a case the rules cannot type, and it does nothing for a two-problem complaint marked ready.

### Ask the model on every case and keep the answer only when it agrees with the rules

This would double the calls and the cost and add no draft the rules could not already make. The two closed questions are asked only where an answer can change the outcome.

## Consequences

Positive:

- A paraphrase the rules miss gets a typed, cited draft instead of an untyped one for manual review, and the reviewer is told which line to check.
- A two-problem complaint is not marked ready.
- The default path, the scored run and CI are unchanged and make no model call.
- Every call is metered, and the evaluation repeats exactly from recordings.
- The output guard also finds restricted values hidden by zero-width characters or typed in full-width digits, a check this work added for the model path.

Negative:

- A live run sends redacted customer lines to the provider. For the capstone the team approved that; a real bank must approve the provider and the data location, and record its own approval, before production use.
- With the hybrid on by default, a machine without the model's key, endpoint or SDK drafts with the rules alone, so its results match the rules-alone column, not the hybrid one.
- A live run depends on the provider. No answer leaves the rules to decide, and a gap case then goes to a person as `ambiguous`.
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
