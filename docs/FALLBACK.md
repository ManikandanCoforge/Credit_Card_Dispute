# Fallback plan: the 6 to 8 minute recording

- Prepared: 2026-10-28 from commit 8553bb36a05ba3b0b6c96b5dffb82aa96c6d7283.
- Owner: Ken (Lead).
- Deadline: record and sound-test before the 2026-10-29 dry run.
- Current numbers: reports/scored-run.md, 12 of 12, 0 format errors, p50 31.000 ms, p95 3670.000 ms, 0.00 USD, 0 model calls.

This is the fallback when the live demo fails. It is not a second demo. Switch once, say why, and play the recording. Do not debug live.

## What exists today

| Artifact | Path | State |
|---|---|---|
| Deck | docs/deck/out/lumen-dispute-copilot-2026-10-29.pdf | Tracked at docs/deck. Rebuilt 2026-10-28 from reports/scored-run.json: 12 of 12, p50 31.000 ms, p95 3670.000 ms. docs/deck/FACTS.md names the source commit (8553bb3) and published run (8c3ac7f). |
| Deck source | docs/deck/out/lumen-dispute-copilot-2026-10-29.pptx | Tracked, built from the same sources as the PDF. |
| Leave-behind | docs/deck/out/lumen-dispute-copilot-leave-behind.pdf | Tracked, same numbers. |
| Current report | reports/scored-run.md | Exists. 12 of 12, 0 format errors. This is the number to quote. |
| Rehearsal record | docs/DEMO_REHEARSAL.md | Exists. Six beats, four arc runs (two before and two after COF-43), 2026-10-28 supplementary checks. |
| Terminal transcript | docs/rehearsal-transcript-2026-10-28.txt | Exists. CARD-D09 duplicate refusal and the policy live-change drill with revert proof. |
| Recording | reports/demo-fallback-2026-10-29.mp4 | **Missing.** No sound-tested video exists. |
| Sound test | none | **Not done.** |

The only video found on this machine (in the main checkout) is docs/poster/out/poster.mp4, which is a poster animation, not the demo. Do not present it as the fallback.

## What is missing, who makes it, and by when

Ken (Lead) must record the full six-beat arc, 6 to 8 minutes, with narration, and store it at reports/demo-fallback-2026-10-29.mp4. Record it before the 2026-10-29 dry run. Test playback on the demo machine and the backup machine, with sound. The recording must show the case ids, the report numbers, the duplicate refusal, and the audit view.

If the recording is still missing at the dry run, say so. Use the captioned terminal transcript and the slides, and do not claim a tested fallback. A text transcript is not a 6 to 8 minute recording.

## Minute marks

| Time | What happens |
|---|---|
| 0:00 to 2:00 | Say what failed and switch. Example: "The mock is not answering on 8765, so I am switching to the recorded run." Name the failing beat once. Do not debug or reset state in front of the assessor. If the recording is missing, say that and switch to the terminal transcript. |
| 2:00 to 6:00 | Play the recorded walkthrough. The intended segments are: CARD-D01 normal draft and approval (about 1:30), CARD-D05 ambiguous and manual_review (about 1:00), CARD-D08 injection not followed or quoted (about 1:00), CARD-D10 503 and retry (about 1:00), CARD-D09 duplicate refusal with 409 duplicate_case (about 1:00), audit view (about 0:30). |
| 6:00 to 8:00 | Questions. Point to reports/scored-run.md for numbers, docs/DEMO_REHEARSAL.md for the rehearsal record, and docs/rehearsal-transcript-2026-10-28.txt for exact output. Name the open gaps: no sound-tested recording, p95 is 3.67 s against the sheet's 2.5 s line, and R2 grounding, R5 deployment transcript and G-03 fresh setup remain open. |

## Live failure ladder

1. Health not 200 or the case list is not twelve: check the port, then switch.
2. Scored run not 12 of 12 or a format error: stop, do not present the arc, switch.
3. A beat fails twice: switch to the recording at that beat; do not improvise a pass.
4. A forbidden or unapproved write, a second record for one logical case, or an audit gap: stop the demo, preserve the state, and report it. Do not edit the audit.
5. The projector or network fails: play the recording from the backup machine.

The full stop-point table is in docs/DEMO_REHEARSAL.md.

## If the recording is missing at the dry run

Use the captioned terminal transcript at docs/rehearsal-transcript-2026-10-28.txt, the six-beat table in docs/DEMO_REHEARSAL.md, and the current report. Walk the table in the same order as the minute marks. Say "the recording is missing" once, at the start, and do not claim it was tested.

The transcript is exact output from 2026-10-28 on port 8855: health 200, twelve cases, the CARD-D09 duplicate refusal, and the policy live-change drill with the checksum revert proof. It is evidence for the mechanics, not a substitute for a narrated recording.

## Do not

- Do not play the poster animation as the demo.
- Quote numbers from the regenerated reports/scored-run.md, not from the deck or the handout: docs/deck is a tracked 2026-10-28 snapshot (12 of 12 at 8c3ac7f) and may be older than the run you just made.
- Do not claim a recording exists, plays with sound, or was tested on the backup machine until it does.
- Do not edit the audit or the report to make a failed beat look passed.
