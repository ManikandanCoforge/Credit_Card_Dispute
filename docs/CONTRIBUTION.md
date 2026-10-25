# Contribution map

Three people, three lanes from the pod operating plan. Each person owns exactly one live-change module for the defence and can explain one end-to-end case without notes.

| Person | GitHub | Pod lane | Live-change module | What they can demo | What they can change live |
|---|---|---|---|---|---|
| Ken | `kenmann01` | Lead: scope, interfaces, rules engine, integration | `src/contract.py`: rules contract and assembly | Build the `CARD-D01` contract from the supplied text: classification, routing, six exact citations, deadline 2026-10-31, and the template narrative. | Change a citation claim and its expectation in a scratch branch, then show the new contract and the focused test result. |
| Mani | `ManikandanCoforge` | Evidence: retrieval, tool client, draft assembly, citations, missing evidence | `src/contract_records.py`: retrieval and tool integration | Run the case list, document reads, and the `transactions` and `merchant` reads, then show one failed case reported while the other cases still build. | Add a tool read or a case-level error reason, then show the mock audit records the read and the remaining cases are unaffected. |
| Zach | `zacharybonagura-coforge` | Eval and operations: harness, CI, cost and latency, deployment, redacted logs, runbook | `tools/evaluate.py`: evaluation harness, gated by `.github/workflows/checks.yml` | Run the evaluator on a submission, show the per-check output and one failing citation, then show the CI job enforcing 100 percent line coverage of `src`. | Add an evaluator check or tighten a CI gate, then show the new report and the workflow result. |

## Why these modules

- **Ken** owns the deterministic rules and assembly surface. The contract shape, classification, routing, citations, deadline, and template narrative meet in `src/contract.py`. That matches the Lead lane for interfaces and the rules engine.
- **Mani** owns the read path. `src/contract_records.py` joins the bank case list, the evidence documents, and the tool responses before assembly. That matches the Evidence lane for retrieval, tool client, and draft assembly.
- **Zach** owns the evaluation and operations gate. `tools/evaluate.py` produces the per-case evidence checks, and the pytest job in `.github/workflows/checks.yml` fails below 100 percent line coverage. That matches the Eval and operations lane for harness and CI.

## Git evidence

Ownership is accountability for the module, not exclusive authorship. The substantive history matches the lanes:

| Module | Ownership evidence |
|---|---|
| `src/contract.py` | Ken, commits `4e684cf` and `01c3044` |
| `src/contract_records.py` | Mani, COF-36 tool-read and case-continuation work in PR #49, re-landed in `01c3044` |
| Evaluation harness: `tools/evaluate.py`, gated by `.github/workflows/checks.yml` | Zachary, commits `664b0f3` and `44799a7`, plus the earlier CI commits |

## Review and demo rules

- One person owns one live-change module. A change that crosses modules still needs the owner's review.
- Every change needs one approval. No direct pushes to `main`.
- Each person can demo their module on the running system, not from slides.
- The shared normal case is `CARD-D01`. Each owner can also explain the case that exercises their module, including the failure or escalation path.
