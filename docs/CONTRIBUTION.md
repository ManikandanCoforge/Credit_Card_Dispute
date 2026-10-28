# Contribution map

Three people, three lanes from the pod operating plan. Each person owns exactly one live-change module for the defence and can explain one end-to-end case without notes.

The repository's rules now live next to this file, not in a scratch directory: `CONTRIBUTING.md` at the root has the branch, commit, gate and review rules, `.github/PULL_REQUEST_TEMPLATE.md` is the pull request body, and `.github/CODEOWNERS` names the reviewer for each path. This file is the lane table they point at.

| Person | GitHub | Pod lane | Live-change module | What they can demo | What they can change live |
|---|---|---|---|---|---|
| Ken | `kenmann01` | Lead: scope, interfaces, rules engine, integration | `src/contract.py`: rules contract and assembly | Build the `CARD-D01` contract from the supplied text: classification, routing, six exact citations, deadline 2026-10-31, and the template narrative. | Change a citation claim and its expectation in a scratch branch, then show the new contract and the focused test result. |
| Mani | `ManikandanCoforge` | Evidence: retrieval, tool client, draft assembly, citations, missing evidence | `src/untrusted.py` and `src/escalation.py`: restricted values, instruction handling, conflict and out-of-scope escalation (PR #52, #53) | Show the cash-withdrawal intake (`CARD-D06`) escalating to `unsupported` with a null deadline, then show a merchant note that tries to give an instruction: it is flagged and never quoted. | Add an instruction phrase or a cash cue, show the escalation test go green, and show which case now routes to `manual_review` instead of being misclassified. |
| Zach | `zacharybonagura-coforge` | Eval and operations: harness, CI, cost and latency, deployment, redacted logs, runbook | `src/resilience.py`: bounded retry, backoff, and circuit breaker (PR #56) | Show a transient tool timeout retried, then the breaker opening after three failures, admitting one probe when half-open, and closing on success. | Change `MAX_ATTEMPTS` or the failure threshold, then show which tests fail and why. |

## Why these modules

- **Ken** owns the deterministic rules and assembly surface. The contract shape, classification, routing, citations, deadline, and template narrative meet in `src/contract.py`. That matches the Lead lane for interfaces and the rules engine.
- **Mani** owns the evidence boundary. `src/untrusted.py` finds restricted values and instruction-shaped evidence, and `src/escalation.py` decides when a case leaves the ordinary path. The read path itself, `src/contract_records.py`, was re-landed from his COF-36 work in PR #49. That matches the Evidence lane for retrieval, citations, and missing evidence.
- **Zach** owns the resilience and CI gate. `src/resilience.py` bounds tool faults, and the pytest job in `.github/workflows/checks.yml` fails below 100 percent line coverage. `tools/evaluate.py` is the supplied grader, unchanged, so it is not presented as his module. That matches the Eval and operations lane for harness and CI.

## Git evidence

Ownership is accountability for the module, not exclusive authorship. The substantive history matches the lanes:

| Module | Ownership evidence |
|---|---|
| `src/contract.py` | Ken, commits `4e684cf` and `01c3044` |
| `src/untrusted.py`, `src/escalation.py` | Mani, PR #52 (conflict and out-of-scope escalation) and PR #53 (untrusted evidence and restricted values) |
| `src/resilience.py` | Zachary, PR #56 (`13d4910`): bounded retry with backoff and a circuit breaker, plus the earlier CI commits `664b0f3` and `44799a7` |

## Review and demo rules

- One person owns one live-change module. A change that crosses modules still needs the owner's review.
- Every change needs one approval, and a "changes requested" blocks the merge. No direct pushes to `main`.
- The reviewer for a path is named in `.github/CODEOWNERS`. That file asks for review; it does not enforce it, because the repository's rulesets are disabled and enabling them is issue #6.
- Each person can demo their module on the running system, not from slides.
- The shared normal case is `CARD-D01`. Each owner can also explain the case that exercises their module, including the failure or escalation path.

## On Windows

The machine the pod develops on is Windows, and three details cost time if they are not known:

- Set `PYTHONUTF8=1` before running anything. Some files are read with the default encoding, which is not UTF-8 on Windows.
- The shell is Git Bash. Native programs such as `git`, `python` and `rg` want `C:/...` style paths, not `/c/...`.
- Do not order rows by `time.time_ns()` in a test. On Windows that clock advances in roughly 1 ms quanta, so calls made in a row can return the same value. PR #76 fixed `tests/test_observability.py` to read span rows by name instead, and `.github/workflows/checks.yml` runs the suite on `windows-latest` so the failure cannot come back unnoticed.
