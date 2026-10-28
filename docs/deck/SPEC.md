# Deck spec: Lumen Bank Dispute Copilot, final demo and technical defense

Presented Thursday 29 October 2026. 16:9, 13.333 x 7.5 in.
Audience: Lumen Bank dispute operations leadership plus Coforge assessors.
Length target: 12 minutes of deck plus 8 minutes of live demo and Q&A.
Every figure in this deck must trace to docs/deck/research/evidence.md. Where a value is marked VERIFY, take it from that file; do not leave the placeholder.

## Story in one line

The copilot does the investigation, cites every fact, and stops at the human. The gate is the product.

## Narrative arc

1. The work before the work (problem).
2. One object, one gate (product).
3. Watch it happen (demo setup).
4. What is proven, exactly (evidence).
5. Why you can trust it (architecture, model boundary, trust boundary).
6. What is not done (honest limits).
7. How it fails and recovers (operations).
8. What comes next (roadmap, pod, ask).

## Visual system (match docs/status and docs/flow plates)

Paper content slides, dark cover and close (the sandwich).
- paper #FBFAF7, card #FFFFFF, sand #F3EFE6, line #E2DDD2, line2 #D3CDC0
- ink #12262E, ink2 #2B454F, muted #68777D
- teal #0D6F6A (primary, 5-10%), teal-soft #E6F2EF
- green #1C7A58, amber #A96900, red #B4452F (risk states only)
- navy #0A1C24 (dark slides), cream #F4EFE3 (text on navy), teal-light #7FBDB4

Type:
- Headline: Georgia, 32-36pt, color ink, line spacing 1.02, left aligned. One sentence, never two lines of equal weight if avoidable.
- Lede: Segoe UI, 15pt, ink2, 1.3 line spacing.
- Body: Segoe UI, 13.5pt, ink2, 1.35.
- Small: Segoe UI 11pt, muted.
- Kicker and metadata: Cascadia Mono, 10pt, uppercase, letterSpacing 1.4, teal or muted.
- Numbers: Georgia 56-64pt teal or ink.

Chrome on every paper slide:
- top hairline at y = 0.62 from x = 0.62 to 12.71
- kicker above it at y = 0.36: "03 · DEMO" left; right side "LUMEN BANK · DISPUTE COPILOT"
- footer at y = 7.06: left "Final demo and technical defense · 29 October 2026", right "[ 04 / 13 ]", mono 9pt muted
- content starts at y = 1.28, left margin 0.62, right margin 0.62

Rules: no shadows, no gradients, no rounded rainbow cards. Hairlines, tinted bands, generous whitespace. At most one image or diagram per slide. No em dashes anywhere.

## Slides

### 01 Cover (navy)
- kicker: LUMEN BANK · DISPUTE OPERATIONS
- title (Georgia 54pt, cream): From complaint to cited draft.
- sub (Segoe UI 20pt, teal-light): A copilot that does the investigation, cites every fact, and stops at the human.
- motif.svg on the right, about 4.2 in wide, or cropped as a large watermark.
- meta row near the bottom, mono 11pt, cream at 70%: FINAL DEMO AND TECHNICAL DEFENSE · 29 OCTOBER 2026 · KANIT · MANI · ZACH
- footnote: Fictional training data. Mock system of record. No customer data.

### 02 The problem (paper)
- section: 01 · THE PROBLEM
- headline: Every complaint restarts the same investigation.
- lede: A handler receives half a story and rebuilds the other half by hand. Which policy applies. Which facts are missing. What the clock says.
- left column, three hairline-separated rows (number, title, one line):
  1. Policy by date. V1 or V2 follows the reported date, never today.
  2. Facts from two systems. Transactions from the bank, context from the merchant.
  3. The clock. Deadline arithmetic decides urgency before anyone reads the prose.
- right column: intake quote on sand, Georgia italic 17pt: "I found a card purchase at Morrow Supplies for 117 crowns. I do not recognize it and need help checking it." Attribution in mono 9pt: CARD-D01-INTAKE, exact line.
- bottom band: mono facts: 12 DEV CASES · 6 TO 9 CITATIONS PER CASE · 27 TOOL ATTEMPTS PER FULL PASS.
- note: the quote must be copied exactly from data/dev; verify against the intake file.

### 03 Product (paper)
- section: 02 · THE PRODUCT
- headline: One contract, six citations, one gate.
- pipeline.svg full width at y about 1.9, height about 3.9.
- three labels beneath, spaced to the four stages: facts freeze; prose may follow; a human opens the door.
- caption: Every case ends in a cited draft waiting for a person, or a named stop. Never a record on its own.

### 04 Demo setup (paper)
- section: 03 · DEMO
- headline: Five complaints. Five ways it can go wrong.
- five rows, each: case chip (mono), title, what you should see, outcome tag.
  - CARD-D01 normal unauthorized: cited draft, approved by the operator, one record created. tag: RECORD
  - CARD-D05 conflicting authorization: the intake says denied, the receipt cannot establish authorization, so it routes to manual review with a null deadline and no record. tag: ESCALATE
  - CARD-D08 merchant note carrying a fake system override: quoted as evidence, never obeyed. tag: REFUSED
  - CARD-D10 transient read failure: two 503 reads, two bounded retries, then a cited draft on the third read. tag: RECOVERED
  - CARD-D09 redelivery of D02 under the same submission reference: no second record, the existing case is returned. tag: DEDUPED
- line at the bottom: The demo runs in the terminal and the mock bank, not in the slides.
- No row depends on an open pull request: all five are on main at 8553bb3.

### 05 Evidence (paper)
- section: 04 · EVIDENCE
- headline: What is proven today.
- six numbers in a 3 x 2 grid, big Georgia numerals, label under each, source line at the bottom.
  - 12 / 12 dev cases pass the evaluator
  - 1014 tests pass
  - 100% line coverage over 3404 statements
  - 27 tool attempts in one full pass, 3 retries
  - 0 model calls on the template path
  - 126 s suite wall time, measured 28 October
- honest line: No case fails. The gaps that remain are named on slide 9, not hidden here.
- source: main 8553bb3 · 28 OCT 2026 · published run at 8c3ac7f · commands in docs/deck/FACTS.md

### 06 Architecture (paper)
- section: 05 · ARCHITECTURE
- headline: Deterministic by design. The model sits outside the decision path.
- figure: docs/status/fig-architecture.png, or a wide redraw if the aspect fights the slide. If used, place at about 8.6 x 6.3 in with a right column.
- right column: THE MODEL IS NOT IN THIS LANE. Classification, routing, facts, citations, deadline come from code. A model may write prose only, after the facts freeze. ADR-001.
- three guarantees in a bottom band: one contract per case; a stop carries a reason; every citation quotes an exact source line.

### 07 Model boundary (paper)
- section: 06 · THE MODEL
- headline: The model answers two closed questions, and nothing else.
- two columns: TEMPLATE PATH (deterministic, 0 calls, the default) vs MODEL PATH (two closed questions, prose only, after the facts freeze). Use ADR-003 facts; label approved or pending accurately.
- centre line, Georgia italic: If the facts are frozen before the model speaks, a bad sentence cannot move a classification, a deadline, or a citation.
- cost and latency: only measured values, else "not measured at volume" in muted.

### 08 Trust boundary (paper)
- section: 07 · TRUST
- headline: Untrusted text is read, never obeyed.
- boundary.svg as the main graphic, about 12.1 x 5.0.
- one real example in a sand box: the D08 merchant note line, in mono, with the caption "stored as a citation, not as an instruction".
- three proofs in a bottom band: exact-slice citations; classification in code; approval hash binds the reviewed draft (403 if it changed).

### 09 Honest limits (paper)
- section: 08 · LIMITS
- headline: What is not done, and why.
- three bands: ON MAIN (12 / 12 cases, the deterministic core and the operator gate), NOT DELIVERED · FOUR NAMED GAPS (reviewer identity, live model route, update and close under Gate U, wrapped customer statement), NOT ATTEMPTED (UI, OCR, adjudication, production deployment).
- warning line: Do not count a gap as delivered.
- dates and PR numbers must match evidence.md.

### 10 Operations (paper)
- section: 09 · OPERATIONS
- headline: It fails in daylight.
- left: the retry ladder as a small stepped graphic: 1 s, 2 s, 4 s, then open the breaker after three exhausted complaints.
- right: four short rows: a stop carries a reason; one redacted meter line per case; 5 audit rows for one hand-walked case; health and reset commands in docs/RUNBOOK.md.
- mono code block with two real commands (runtime.py pending, approve, audit), 11pt, on navy.

### 11 Roadmap (paper)
- section: 10 · ROADMAP
- headline: The next 30 days, in order.
- five numbered rows with effort: reviewer identity (M1); approve the model route with measured cost and latency; real intake pilot with two analysts; the next two complaint types; ruleset enforcement, blocked by the GitHub plan.
- right rail, mute: 60 and 90 day items in one line each.

### 12 Pod (paper)
- section: 11 · THE POD
- headline: Three people, one system, defended line by line.
- three columns, each: name, role, what they built, one thing they can change live.
- contents from defense.md, verified against git log.

### 13 Close (navy)
- headline (Georgia 46pt, cream): The gate is the product.
- three asks, numbered, short:
  1. Approve the model route for the two closed questions.
  2. Name the next two complaint types to productize.
  3. Give us two analysts for a 30-day intake pilot.
- thanks line and Q&A prompt, mono.
- motif reused small.

### Appendix (optional, paper, 2-3 slides)
- A1: The contract, verbatim. A trimmed JSON excerpt from the published run for D01, mono, with callouts for the six citations.
- A2: The 12 dev cases. Table: id, classification, route, pass, citations, reason.
- A3: Sources and commands. The exact commands behind every number.

## Build notes

- Use pptxgenjs 4.0.1. Copy tooling from ~/.dsh/skills/pptxgenjs-decks.
- Speaker notes on every slide, 3-6 sentences of spoken text, from defense.md.
- Keep every constant (numbers, sha, dates) in docs/deck/FACTS.md, the one file the copy is checked against.
- No text under 10pt. No paragraph under 1.15 line spacing.
- Export PDF with LibreOffice; keep the deck under 1.5 MB if possible.
