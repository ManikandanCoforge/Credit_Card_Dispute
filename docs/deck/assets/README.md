# Hero assets: Lumen Bank dispute copilot

Three vector plates and their 2x raster renders, in the deck print system: paper, hairline rules, tinted bands, Georgia headlines, Segoe UI body, Cascadia Mono metadata. No shadows, no gradients.

## Files

| File | Canvas (SVG) | PNG | Aspect | Use |
|---|---|---|---|---|
| `pipeline.svg` / `pipeline.png` | 3200 x 1100 | 6400 x 2200 | 2.909:1 | Slide 03, the four-stage run |
| `boundary.svg` / `boundary.png` | 3200 x 1400 | 6400 x 2800 | 2.286:1 | Slide 08, the trust boundary |
| `motif.svg` / `motif.png` | 1600 x 1600 | 3200 x 3200 | 1:1 | Cover mark, navy slide |
| `build_assets.py` | | | | Generator for all six files |
| `README.md` | | | | This file |

The two plates are 6400 px wide, which is 480 ppi at 13.333 in. The motif is 3200 px square, which is 762 ppi at 4.2 in. The SVGs are the source of truth; the PNGs are for paste-in and preview.

## Title and caption intent

| Asset | Title inside the plate | Caption or deck line |
|---|---|---|
| Pipeline | A case list becomes one record. | Every case ends in one of two states: a cited draft waiting for a person, or a stop with a named reason. Never a record on its own. |
| Boundary | Untrusted text in. A code gate out. | Text is quoted. Code decides. A human approves. |
| Motif | None, by design. Alt text: One route, one stop. | None. |

The pipeline caption is the slide 03 caption in `docs/deck/SPEC.md`. The boundary caption is already printed in the plate, bottom right. The motif is textless so the cover headline stays the only voice.

## Mount guidance for 13.333 x 7.5 in

Margins are 0.62 in. The plate header and headline are part of the artwork, so either use the plate full-bleed and drop the duplicate deck headline, or keep the deck headline and treat the plate headline as a subordinate deck line.

- Pipeline: place at x 0.62, y 1.95, size 12.09 x 4.16 in. Bottom edge 6.11. The optional caption sits at 6.35, single line, 13.5 pt. Do not stretch past 12.09 in or the right footnote crowds the edge.
- Boundary: place at x 0.62, y 1.68, size 12.09 x 5.29 in. Bottom edge 6.97, just above the footer. This is the largest honest size; there is no room for a caption below. If a caption is required, use 11.4 x 4.99 in at x 0.97, y 1.78, bottom edge 6.77, caption at 6.95.
- Motif: place at 4.2 x 4.2 in on the right of the navy cover, for example x 8.5, y 1.55. The navy background is part of the file, so place it flush with the slide, not inside a card. For a watermark, scale to 13.333 in wide and center-crop vertically; keep the amber node in frame.

Type at the mounted size: pipeline body about 8.2 pt, boundary body about 7.1 pt. That is leave-behind scale, not back-of-room scale. On screen, the shapes and the two red stops carry the slide; the detail is for the handout.

## Regenerate

```bash
cd D:/20-projects/credit-card-dispute
python docs/deck/assets/build_assets.py
```

The script writes the three SVGs, then screenshots each SVG directly at 2x with headless Chrome and prints the PNG size read back with Pillow. Chrome runs with an explicit profile under `assets/_chrome` (override with `DECK_CHROME_PROFILE`) because the default profile is locked on this machine; the old HTML wrapper crash is gone. If Chrome is missing it falls back to Edge. The shared project venv has no Pillow, so run this script with the system `python` (C:/Python314), which has Pillow 12.2.0. cairosvg was tried first and failed at import because the cairo DLL is not present. sharp-cli and resvg are not installed.

## Source of the strings

Every visible value was taken from the repository, not invented.

- Pipeline: `docs/deck/FACTS.md` and `reports/scored-run.json` at main `8553bb3`: 12 of 12 dev cases build a contract, 27 tool attempts, 3 retries, 0 model calls, six to nine citations per case, and the 201 / 200 / 403 / 409 responses. The D01 sha256 `af65f68659d94274382d90d07417c94031d0c574722bd7b8850e7700ce13ebd4` is reproduced from a fresh mock on 2026-10-28 and matches rehearsal runs 3 and 4. It is shown in full, not as an ellipsis.
- Boundary: the merchant key count; `tools/runtime.py` for `digest()`, the 403 `approval_missing_or_draft_changed` and 409 `duplicate_case`; `src/contract.py` for the exact-slice rule. The audit count is 5 on the clean walk (2 tool_read, review_requested, human_approved, record_created), per `docs/DEMO_REHEARSAL.md`.
- Test figures on the boundary are main `8553bb3` on 2026-10-28: 1014 tests, 100.00 percent line coverage over 3404 statements. The older 254 / 718 figures belong to `df3daa4` and are not used here.
- Motif: no copy.

## Honest limits, as drawn

- 12 of 12 dev cases build a contract, with 0 stops. D05 and D06 route to manual review because the evidence does not decide the answer. D07 and D10 retry and then build. D09 is refused as a duplicate.
- The review and record endpoints are wired operator steps; the presenter or operator runs them, never the agent. The scored run stops at the draft.
- #52 (escalation and untrusted evidence), #63 (review gate) and #65 (model route, off by default) are merged on main. #66 is closed; its meters landed through COF-43. Zero pull requests are open.
- No model call is on the read path. Classification, routing, facts, citations and deadline come from code.

## Design tokens

Paper `#FBFAF7`, ink `#12262E`, ink2 `#2B454F`, muted `#68777D`, line `#E2DDD2`, line2 `#D3CDC0`, sand `#F3EFE6`, teal `#0D6F6A`, teal-soft `#E6F2EF`, green `#1C7A58`, red `#B4452F`, red-soft `#F8ECE8`, amber `#A96900`, navy `#0A1C24`.

Georgia for headlines, Segoe UI for labels and body, Cascadia Mono for metadata, uppercase and letterspaced. Windows fallbacks are declared in `build_assets.py`, so the SVG renders correctly without web fonts.