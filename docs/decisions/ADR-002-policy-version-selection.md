# ADR-002: Policy version selection

- Status: Accepted
- Date: 2026-10-25
- Ticket: COF-47
- Owner: Mani (ManikandanCoforge)
- Related: `docs/POLICY_GUIDE.md`, `docs/OUTPUT_CONTRACT.md`, `src/build_records.py`, `src/contract.py`

## Context

The supplied policy has two versions with fixed 2026 windows:

| Version | Effective from | Effective through | Unauthorized deadline days |
|---|---|---|---:|
| `CARD-POLICY-V1` | 2026-01-01 | 2026-08-31 | 20 |
| `CARD-POLICY-V2` | 2026-09-01 | 2026-12-31 | 30 |

Both versions say to select the policy using the Reported date, not the transaction date or system time. `CARD-PROCEDURE-01` applies to both versions.

A complaint can be reported after the charge posted, and a report can arrive after a newer policy is in force. The supplied dev set already contains this case: `CARD-D11` reports 2026-08-31, while `CARD-POLICY-V2` exists in the same policy directory. The decision therefore cannot use the newest file, the file timestamp, today's date, or the transaction date.

## Decision

Select the policy version by the complaint's Reported date, never transaction date or system time. A historical report keeps the version in force on its reported date even after a newer version exists.

The rule is:

1. Read `Reported date` from the intake.
2. Select exactly one policy version whose effective window contains that date, inclusive of both ends.
3. Select the procedure named by that version.
4. If no version matches, or more than one version matches, leave both policy ids empty and let contract assembly fail closed.
5. Calculate the deadline from the reported date plus the day count in the selected version, with the reported day as day zero.

The selected version's id appears in `policy_ids` and in the deadline citation. The approval hash therefore covers the exact version that was in force, not whichever policy happens to be newest when the draft is created.

## Implementation anchors

| Concern | Anchor |
|---|---|
| Read the reported date from the intake | `src/build_records.py` `_intake`, `_field`, `_day` |
| Parse effective windows and procedures | `src/build_records.py` `_policy_versions`, `_PolicyVersion` |
| Match the window | `src/build_records.py` `_policy` |
| Require both ids before assembly | `src/contract.py` `assemble_contract` |
| Calculate the deadline | `src/contract.py` `_deadline` |

`_policy_versions` reads every `*.md` policy file and parses `Effective from` and `Effective through`. It rejects a file whose declared source id does not equal the file stem, or whose end is before its start; a date that does not parse raises instead of being skipped. It does not use file order or modification time.

`_policy` keeps a version only when `start <= reported <= end`. It returns both ids as null when the match count is not exactly one. That covers a missing reported date, a date before every window, a date after every window, and overlapping windows. The selection code makes no call to the system clock.

`assemble_contract` refuses to build a contract when either policy id is null and raises `ContractError`. A missing policy is never filled with a guess. `contract_records.py` then reads the selected policy and procedure files by id, so the citation text comes from the same version that was selected.

The boundaries are inclusive:

- `2026-08-31` belongs to `CARD-POLICY-V1`.
- `2026-09-01` belongs to `CARD-POLICY-V2`.

Examples from the supplied fixtures:

| Case | Reported date | Selected version | Unauthorized days | Deadline |
|---|---|---|---:|---|
| `CARD-D01` | 2026-10-01 | `CARD-POLICY-V2` | 30 | 2026-10-31 |
| `CARD-D11` | 2026-08-31 | `CARD-POLICY-V1` | 20 | 2026-09-20 |

`CARD-D11` is the stale-policy regression case. It must keep version 1 after version 2 is published. The policy file itself states that a newer policy does not supersede a historical effective period.

The selection is covered by `tests/test_build_records.py`: `test_card_d01_records_policy_version_2`, `test_card_d11_records_policy_version_1`, `test_reported_date_before_every_window_leaves_policy_empty`, `test_reported_date_after_every_window_leaves_policy_empty`, and `test_reported_date_inside_two_windows_leaves_policy_empty`.

## Rejected alternatives

### Always use the newest policy

Use the highest version id, the last file, or the most recently modified policy file.

Rejected. It gives a historical report rules that were not in force on its reported date. For `CARD-D11`, the newest policy would select `CARD-POLICY-V2`, cite the 30-day line, and produce 2026-09-30 instead of the correct 2026-09-20 from version 1. The policy id and citation would also be wrong. That is exactly the stale-policy case the exercise supplies.

File order and modification time are also not evidence. `docs/POLICY_GUIDE.md` states that effective dates are authoritative and file ordering is not. The file system is not a policy register.

### Use the system date

Select the version that covers today, or pass the current clock into the selector.

Rejected. The same complaint would produce different policy ids, citations, and deadlines on different days. A replay in 2027 could select no version at all. The scenario dates stay fixed in 2026, and the assessment runs against historical reports. An audit that stores the draft hash could not reproduce the decision after the clock moved or a third version shipped.

### Use the transaction date

Select the window that contains the charge's posted date, because the dispute is about the charge.

Rejected. The charge date and the report date answer different questions. A late report can fall in a later policy window, and the policy text names the Reported date. Using the posted date selects the wrong version and changes both the deadline and the citation. The transaction row remains evidence for the charge; it is not the policy selector.

### Guess the nearest version or default to version 1

If no window matches, pick the closest one or keep the last known good version.

Rejected. This invents a policy that the supplied sources do not support. `docs/POLICY_GUIDE.md` requires disclosure and escalation when the required policy cannot be established; the contract layer raises `ContractError` instead of filling the ids. Honest escalation is preferable to a plausible but wrong rule.

## Consequences

Positive:

- A historical report keeps its historical rules.
- The policy id, citation, and deadline come from one version.
- The same evidence and reported date always produce the same selection.
- A report outside every window fails closed and can be escalated rather than silently governed by a newer version.

Negative:

- Every new policy version must declare a non-overlapping effective window, or the selector returns no version for the overlap.
- A report date that is missing or malformed stops contract assembly. That is deliberate, but it means intake completeness matters.
- The policy directory is the source of truth, so a broken or misnamed policy file can remove a valid window. A misnamed or reversed file is skipped rather than reported: if no other file matches the reported date, assembly fails closed, but if another file matches, the bad file is silently absent.

## Review triggers

Revisit this decision if any of the following changes:

- The bank introduces a policy register, effective-time timestamps, or a supersession rule that differs from the supplied windows.
- A case requires a policy version that was withdrawn or corrected after the report.
- The output contract starts requiring the policy version's effective dates in addition to its id.
- A third policy version is added and the windows touch or overlap.
