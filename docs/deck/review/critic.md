> **HISTORICAL, 27 October 2026.** This critique reviews the pre-rebase deck at
> `df3daa4` and its numbers (7 of 12, 254 tests, 25 audit rows, the D09/PR 66
> mix-up). The deck was rebuilt on 28 October against main `8553bb3` and the
> published run; the issues below were the input to that rebuild, not open work.
> Current numbers: `docs/deck/FACTS.md`. Current deck: `out/lumen-dispute-copilot-2026-10-29.pdf`.

# Deck critique: lumen-dispute-copilot-2026-10-29.pdf

Reviewed 2026-10-27. I re-rendered all 16 pages at 150 dpi from the 01:34 PDF; the render set already on disk was stamped 01:30 and the deck was rebuilt after it, so quotes below come from the current PDF only. I read the pptx speaker notes, FACTS.md, evidence.md, defense.md and docs/ASSESSMENT.md, and I checked every code claim against .worktrees/deck-main at df3daa4. The smallest type anywhere in the deck is 10 pt (measured span by span), so the "unreadable from 1 m" worry does not survive measurement: the problems here are status, numbers and framing, not legibility.

## 1. VERDICT

It passes the rubric as written, around the 75 percent anchor (core behaviour with explainable limitations), with all six critical gates intact on the evidence shown. The single weakest thing is slide 4, the page that promises "five honest labels", because the D09 row attaches its fix to pull request 66 ("the excerpt join waits on 66", status "ON MAIN · DRAFT 66", and the note says "D09 needs 66 for the redelivery path") while FACTS.md L56 says 66 is the meters PR, so the first assessor who opens the PR list catches the deck in the one sin it claims to have solved. Fix that row and the meter line on slide 10 before Thursday and nothing else stands between this deck and a pass.

## 2. BLOCKERS

Item numbers are the priority order for Tuesday night. Blockers are 1 to 7; 8 to 12 are moves and cuts in sections 3, 4 and 7.

### 1. Slide 4, the status column is still not five honest labels

Quotes: "Dedupe runs on main; the excerpt join waits on 66." with status "ON MAIN · DRAFT 66", and the speaker note "D09 needs 66 for the redelivery path."

Check: FACTS.md L56 says "#66 meters (CHANGES_REQUESTED)". Slide 9 says the same ("#66 Meters with route, tool attempts and retry count."). defense.md Q2 says the D09 citation join "has no PR yet". So the slide and the note both attach D09 to a PR that is about metering.

Must become: "Dedupe runs on main; the excerpt join has no pull request yet." Status "ON MAIN · STOPS". Note: "D09 needs a citation join that has no PR yet."

Second defect on the same column: D10 and D09 are FAIL on main (slide 15) yet their statuses lead with "ON MAIN" ("ON MAIN · RETRY 56", "ON MAIN · DRAFT 66"), which is the same token D01 and D08 get for passing. Must become three values only: "ON MAIN" (pass), "ON MAIN · STOPS" (fail on main), "IN REVIEW · 52" (fixed on a branch). D10 becomes "ON MAIN · STOPS".

Third, the D01 cell: "Review requested, hash bound, record written. 201, then 200, then 409." drops the 403, which is the gate the slide is about. Must become: "201, then 200 replay; 403 on a changed field; 409 on a second record." (FACTS.md L39-42.)

### 2. Slide 10, the meter claims two fields it does not have

Quote: "Path, duration, tool calls, cost. Text is redacted before it is written."

Check: reports/scored-run-meters.json rows carry exactly case_id, duration_ms, model_calls, model_tokens_in, model_tokens_out, cost_usd, path (tools/scored_run.py:107-116). There is no tool-call field, no text field, and the string "redact" appears nowhere in src/, tools/ or reports/ at df3daa4. Slide 9 itself says tool attempts and retry count are what #66 adds.

Must become: "Path, duration, model calls, tokens, cost. No case text is written to the meter." If you want the stronger claim, it belongs under #66 on slide 9 as a proposal, not on 10 as shipped.

### 3. Slide 11, the roadmap never closes D09

Quote: "Four moves, ordered so each one unblocks the next." The moves are 01 "Land 52 and 63." (D05, D06), 02 "Wire 56 into the tool read." (D07, D10), 03 the model route, 04 the pilot.

Check: slide 15 shows D09 FAIL on COF-43, and no move names it. Four of the five named stops get a home; the fifth gets silence. An assessor counts five failures on slide 15 and four fixes here.

Must become: a fifth line, "05 · Close D09's excerpt join (COF-43). No branch yet. One day to join the statement, two to review the sheet.", or a footnote carrying the same fact and date. Also give move 01 an exit criterion, "lands 9/12 on the #52 branch" (defense.md Q2), so the roadmap has a measurable step.

### 4. Slide 16, the command block does not run as printed

Quote: "cd .worktrees/deck-main" then "python -m pytest -q", "python tools/scored_run.py", "bash docs/deck/build/build.sh".

Check: (a) .worktrees/deck-main has no docs/deck directory (verified: the path does not exist), so build_assets.py and build.sh cannot run from there; (b) tools/scored_run.py defaults to --base-url http://127.0.0.1:8899 (tools/scored_run.py:665-668) while tools/runtime.py serve defaults to port 8765 (tools/runtime.py:179) and no serve command is shown, so the scored run has nothing to talk to; (c) FACTS.md L11 runs pytest through the .venv python, not bare python.

Must become: two blocks. Numbers, from the worktree: "python -m tools.runtime serve --data data/dev --state .state/mock.sqlite3 --port 8899 &", then "python tools/scored_run.py --base-url http://127.0.0.1:8899". Deck rebuild, from the repo root, where docs/deck actually lives: "bash docs/deck/build/build.sh". Use the venv path on the pytest line.

### 5. Slide 7, present tense on an unmerged path

Quote: "The model answers two closed questions, and nothing else." with the right-hand card reading "Proposed, changes requested, not on main."

Must become: "Once approved, the model answers two closed questions. Nothing else." The deck spends slide 9 insisting "DO NOT COUNT THE IN-REVIEW BAND AS DELIVERED"; the headline of 7 should not contradict that in the tense of its main verb.

### 6. Slides 3 and 14, the key count

Quote: "CONTRACT · CARD-D01 · 10 KEYS" above a table with seven rows, and the note says "Ten keys".

Check: src/contract.py:144-155 does have 10 fields (case_id, classification, routing, policy_ids, facts, missing_information, deadline, citations, follow_up_questions, narrative), so 10 is true and the page simply does not show it. A1 shows 8 fields and calls only the citation array abbreviated while dropping missing_information and follow_up_questions.

Must become: either chip "10 KEYS · 7 SHOWN" on 3 and subtitle "with citations, missing_information and follow_up_questions abbreviated" on 14, or add the three rows. Separately, A1's line "citations": [ 6 claims, 5 source ids ], is not valid JSON inside a JSON-shaped block. Replace it with one real citation object plus an ellipsis, or label the block pseudo-JSON.

### 7. Slide 5, 18.2 is the one number FACTS tells you to round

Quote: "18.2 / SUITE, SECONDS / Coverage gate fails below 100%."

Check: FACTS.md L10: "18 s (17.58 s on the lead's run, 18.22 s on the evidence run; say 18 s)". The deck is the only artifact printing the unrounded evidence-run figure, and it prints it to three significant figures.

Must become: "18". Also move the caption: "Coverage gate fails below 100%" describes the 254 tile, not the seconds tile, and each tile's caption should describe its own number.

## 3. RUBRIC COVERAGE

| Rubric line | Carried by | Would a skeptic be satisfied | Gap |
| --- | --- | --- | --- |
| Value | 2, 3, 5 | No | Every number is a build number (7/12, 7.65 ms, 254 tests). Nothing states what changes for an analyst or for the queue, and no slide says the minutes are unmeasured (defense.md Q5 says it out loud; no page does). The ops lead's question is never answered. Item 11. |
| Limitations | 9, 15, 5 footer, 8 strip | Yes, strongest line in the deck | Three bands, proposed-not-agreed said twice, dormant retry named as dormant. Nothing to fix. |
| Justified choices | 6, 7, 8, ADR-001 footer | Mostly | The three big choices are argued: deterministic core, model outside the path, text as data. Nothing justifies the deployment shape (one node, one SQLite file, no reviewer identity), which defense.md L6 and Q13 own verbally and the deck leaves to a "NOT ATTEMPTED" line. Add four words to 9's NOT ATTEMPTED row: "single node, SQLite, no identity". |
| Individual understanding | 12 | Thin | One paragraph per person, a seam each, and the cryptic label "CAN CHANGE LIVE" ("the retry budget"). Nothing on the page suggests any of them can answer a question about another's module, which is the hidden test. Item 12. |
| Roadmap | 11, 13 | Partly | Ordered and dated, which is more than most decks manage. But no owner per move, no exit criterion, and D09 has no move at all. Items 3 and 11. |

The other five dimensions, scored on the written evidence: workflow and domain (3, 6, 14) is strong; grounding (3, 8, 15) is strong; tools and boundaries (6, 8, 10) is strong apart from the meter overclaim; evaluation (5, 15) is strong; deployment and operation (10, 16) is the weakest, and the broken command block on 16 is why.

### 11. RUBRIC: the value gap, one line on slide 13

Slide 13 asks for two analysts and thirty days but never says what the pilot is for. Add one line under the asks: "We have not measured analyst minutes, so we are not claiming any. The pilot's first output is that number." That is the honest version of defense.md Q5, it answers the ops lead's question with a limitation instead of a fabricated metric, and it turns the deck's weakest rubric line into a strength.

### 12. RUBRIC: slide 12 needs one question per person

Quote: "CAN CHANGE LIVE" above "the retry budget", "the escalation rule", "the dev case list".

The label is cryptic (change it to "If you push on this, he can change it live", or delete it) and the page proves ownership, not depth. Add one hard question each person will answer, printed small: Zach, "why three attempts and waits of one second then two?"; Mani, "what happens when a follow-up names a document the read step cannot load?"; Kanit, "what stops a changed draft from being written?". That is the hidden test made visible.

## 4. ARC

The order is earned: problem, object, demo map, proof, mechanism, boundary, limits, operations, plan, pod, ask. Three things do not earn their place: the first two are items 8 and 9, the third is the redundancy behind item 10 in section 7.

### 8. Slide 2 states the problem as mechanics, not as the client's queue

Quote: "Half the story is rebuilt by hand before anyone can decide it." plus the footer "12 DEV CASES · 6 SOURCES NAMED PER CASE · 20 TOOL READS · 0 MODEL CALLS".

The three left-hand blocks explain how the investigation works, not what it costs. The sentence an ops lead needs is about waiting: every case sits in the queue while someone rebuilds the same five sources by hand. Rewrite the subtitle to name the queue, and delete the footer strip, which on a problem slide argues the opposite of the headline and repeats numbers that slide 5 owns.

### 9. Slide 4 uses slide 9's vocabulary five pages early

Quote: "IN REVIEW · 52" and "ON MAIN", on a page that comes before slide 9 defines the bands ("Three bands. The middle one is not delivered.").

A reader who stops at 4 concludes that three of five cases are shipped. Add one legend line under the table: "ON MAIN = on df3daa4 today. IN REVIEW = works on an open pull request, not on main." That also makes item 1's status fix self-explanatory.

## 5. PACING

1034 words of speaker notes at 140 words per minute is 7 min 24 s against SPEC.md's 12-minute deck target (plus 8 minutes of demo and Q&A). The deck is 4.6 minutes under its slot, not over, so the risk is not a slide running away; it is four minutes of unscripted filling, and it will happen on the two slides with the most content per scripted word:

1. Slide 8 (80 words, 34 s). Three columns, four controls, and the boundary argument. This is where the presenter will improvise the D08 story and lose two minutes.
2. Slide 6 (65 words, 28 s). Four columns, two exception funnels, and a figure that must be traced left to right.

Slide 4 is not a pacing problem but a scheduling one: defense.md puts seven and a half demo minutes there, so the 12-minute deck clock is really 12 plus 8, and 4's 31 s of notes is the only slide that will be almost entirely live.

## 6. THREE HARD QUESTIONS

1. "Your slide 15 shows five failures, each with a ticket. Your roadmap fixes four. Which move closes COF-43 for D09, and what date do you attach to it?" It should be answered on slide 11, and currently cannot be.
2. "Show me one meter line and point at the tool calls and the redaction step you named on slide 10." It should be answered on slide 10, and currently the file has neither field.
3. "When the changed-field 403 fires, the mock writes an audit row. Why is that row evidence of a control and not an attempted unapproved write?" It should be answered on slide 3, where the hash binding lives, with one line borrowed from slide 10's audit panel. defense.md already warns against staging this 403 live; an assessor who reads the audit will ask it anyway.

## 7. WHAT TO CUT

### 10. Cut one page, two strips and one tile

- Cut slide 7 as a page. Slide 6's second headline already says "The model sits outside the decision path", and slide 9 already says #65 is in review. Fold the template-path sentence into 6's footer and the ADR-001 line into 9's #65 row. This buys the minute that 8 needs.
- Cut the "18.2" tile on slide 5 (item 7), leaving five tiles that each measure something.
- Cut the footer strips on 2 and 6 (item 8). Slide 5 owns those numbers.
- Trim slide 13: "Approve the model route for two closed questions." and "Two analysts for a 30 day intake pilot." are slide 11's moves 03 and 04 restated. Keep 13 as a callback, not a second list.
- Do not cut slide 12. It is the only page carrying individual understanding, even if it needs item 12's depth.

## Numbers checked

- 7/12 and 0 format errors: FACTS.md L15. Match.
- 254 tests, 718 statements, 100.00 percent: FACTS.md L10. Match.
- 7.65 ms p95, 6.4 to 7.7 per case: FACTS.md L16. Match.
- 20 reads, 9 merchant and 11 transactions: FACTS.md L18. Match.
- 0 model calls, 0.00 USD, 12 of 12 rows: FACTS.md L17. Match.
- 6 citations from 5 sources: FACTS.md L18. Match on 3 and 14.
- 18.2 s: FACTS.md L10 says "say 18 s". Does not match, item 7.
- 5 audit rows and hash 96dec7d3...b198: FACTS.md L43. Match on 3, 8, 10.
- 20 merged, 4 open: FACTS.md L19. Match on 9 and 12.
- 945 lines on #63: FACTS.md L54. Match.
- 488, 279, 128, 192 lines: evidence.md L64 (not in FACTS.md). Match on 16.
- 201, 200, 403, 409: FACTS.md L39-42. Match on 10; the D01 cell on 4 omits the 403.
- #52, #63, #65, #66 statuses: FACTS.md L53-56. Match on 9; 66 is misattributed on 4.
- "6 sources named per case": FACTS.md L50. True of the dataset, but 3 and 14 say 5 sources for the citations. Not a contradiction once you know source documents and cited sources are different things, but a reader will ask.

One correction for the number sheet, not the deck: slide 10 prints "RETRY LADDER: 3 ATTEMPTS, WAITS OF 1 S THEN 2 S", which matches the code and evidence.md L70. FACTS.md L32 says "1s/2s/4s". The deck is right and FACTS.md L32 should be corrected before anyone quotes it.