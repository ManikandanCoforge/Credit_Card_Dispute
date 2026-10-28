
// docs/deck/build/build.js. Lumen Bank dispute copilot, final deck.
// Deterministic: node build.js writes out/lumen-dispute-copilot-2026-10-29.pptx
// Numbers trace to docs/deck/FACTS.md at origin/main 8553bb3.
const path = require("path");
const pptxgen = require("pptxgenjs");
const { COLORS, FONT, W, H, M, text, rule, chrome, headline, eyebrow, chip } = require("./theme");

const TOTAL = 16;
const GEN = (f) => path.join(__dirname, "gen", f);
const ASSET = (f) => path.join(__dirname, "..", "assets", f);
const OUT = path.join(__dirname, "..", "out", "lumen-dispute-copilot-2026-10-29.pptx");

// ---- local helpers -------------------------------------------------------
function hFor(str, fs, w) {
  const cpl = Math.max(8, ((w - 0.04) * 72) / (0.56 * fs));
  const lines = str.split("\n").reduce((a, p) => a + Math.max(1, Math.ceil(p.length / cpl)), 0);
  return (lines * fs * 1.28) / 72 + 0.06;
}
function para(s, str, x, y, w, o) {
  o = o || {};
  const fs = o.fs || 13.5;
  const h = o.h || hFor(str, fs, w);
  const opts = { x, y, w, h, fontSize: fs, color: o.color || COLORS.ink2, fontFace: o.font || FONT.body,
    lineSpacingMultiple: o.ls || 1.22, valign: o.valign || "top", align: o.align || "left" };
  if (o.italic) opts.italic = true;
  if (o.charSpacing) opts.charSpacing = o.charSpacing;
  text(s, str, opts);
  return y + h;
}
function mono(s, str, x, y, w, o) {
  o = o || {};
  return para(s, str, x, y, w, Object.assign({ fs: 10, font: FONT.mono, color: COLORS.muted, ls: 1.25 }, o));
}
function card(s, x, y, w, h, fill, lineColor) {
  s.addShape("rect", { x, y, w, h, fill: { color: fill || COLORS.card }, line: { color: lineColor || COLORS.line, width: 0.75 } });
}
function headerRow(s, y, cells) {
  cells.forEach((c) => mono(s, c.t, c.x, y, c.w, { align: c.align || "left", color: COLORS.muted, charSpacing: 1.2 }));
}
function notes(s, t) { s.addNotes(t); }

// ---- slides --------------------------------------------------------------
function s01_cover(pres) {
  const s = pres.addSlide();
  s.background = { color: COLORS.navy };
  text(s, "LUMEN BANK  ·  DISPUTE OPERATIONS", { x: 0.9, y: 0.85, w: 7.6, h: 0.22,
    fontFace: FONT.mono, fontSize: 10.5, color: COLORS.tealLight, charSpacing: 1.4 });
  text(s, "From complaint to", { x: 0.9, y: 1.45, w: 7.6, h: 1.0, fontFace: FONT.head,
    fontSize: 54, color: COLORS.cream, lineSpacingMultiple: 0.98 });
  text(s, "cited draft.", { x: 0.9, y: 2.52, w: 7.6, h: 1.0, fontFace: FONT.head,
    fontSize: 54, color: COLORS.tealLight, lineSpacingMultiple: 0.98 });
  para(s, "A copilot that does the investigation, cites every fact, and stops at the human.",
    0.9, 3.8, 6.4, { fs: 20, color: "A9BEC2", ls: 1.25 });
  rule(s, 0.9, 5.0, 3.2, "1E3A44", 1);
  mono(s, "FINAL DEMO AND TECHNICAL DEFENSE  ·  29 OCTOBER 2026  ·  KANIT, MANI, ZACH",
    0.9, 5.18, 7.45, { fs: 10.5, color: "9DB0B4", charSpacing: 0.6 });
  mono(s, "Fictional training data. Mock system of record. No customer data.",
    0.9, 6.5, 7.6, { fs: 10, color: "6E8388" });
  s.addImage({ path: ASSET("motif_alpha.png"), x: 8.45, y: 1.55, w: 4.2, h: 4.2 });
  mono(s, "[ 01 / 16 ]", 11.0, 6.5, 1.71, { fs: 10, color: "6E8388", align: "right" });
  notes(s, "Thank you for the time. This is the Lumen Bank dispute copilot, presented as a working system, not a concept. The claim on this slide is narrow on purpose: a complaint becomes a cited draft, and a person makes the decision. Everything later traces to one commit, 8c3ac7f, on main at 8553bb3. The data is fictional and the system of record is a mock.");
}

function s02_problem(pres) {
  const s = pres.addSlide();
  s.background = { color: COLORS.paper };
  chrome(s, 2, TOTAL, "01 · THE PROBLEM");
  headline(s, "Every complaint restarts the same investigation.", { y: 1.05, w: 8.2, h: 1.34 });
  para(s, "Every case sits in the queue while someone rebuilds the same five sources by hand.", M, 2.46, 6.95, { fs: 15, color: COLORS.ink });
  const rows = [
    ["POLICY BY DATE", "Version 1 or version 2, chosen from the reported date, not the date of the call."],
    ["FACTS FROM TWO SYSTEMS", "The merchant record and the transaction record are two stores with two shapes."],
    ["THE CLOCK", "A deadline is counted from the reported date, and a day count can be wrong by one."],
  ];
  rows.forEach((r, i) => {
    const y = 3.44 + i * 1.0;
    rule(s, M, y, 6.5, COLORS.line, 0.75);
    eyebrow(s, r[0], { x: M, y: y + 0.1, w: 6.2, color: COLORS.teal });
    para(s, r[1], M, y + 0.32, 6.4, { fs: 13.5 });
  });
  rule(s, M, 6.42, 6.5, COLORS.line, 0.75);
  s.addShape("rect", { x: 7.62, y: 3.44, w: 5.09, h: 2.98, fill: { color: COLORS.sand }, line: { color: COLORS.line, width: 0.75 } });
  para(s, "\u201cI found a card purchase at Morrow Supplies for 117 crowns. I do not recognize it and need help checking it.\u201d",
    7.92, 3.66, 4.5, { fs: 17, font: FONT.head, italic: true, color: COLORS.ink, ls: 1.2 });
  mono(s, "CARD-D01-INTAKE  ·  UNTRUSTED TEXT", 7.92, 6.0, 4.5, { fs: 10, color: COLORS.muted, charSpacing: 1.1 });
  notes(s, "Start with the work as it is done today. One complaint carries an intake statement, an attachment, two systems of transaction data, and a policy set chosen by date. Analysts rebuild that map by hand, per case. The words on the right are the whole input for case D01: a card purchase at Morrow Supplies for 117 crowns. That sentence is untrusted text.");
}

function s03_product(pres) {
  const s = pres.addSlide();
  s.background = { color: COLORS.paper };
  chrome(s, 3, TOTAL, "02 · THE PRODUCT");
  headline(s, "One contract, six citations, one gate.", { y: 1.1, w: 12.0, h: 0.7 });
  para(s, "The object's shape is fixed before any prose exists.", M, 1.88, 10.5, { fs: 15, color: COLORS.ink });
  card(s, M, 2.4, 7.55, 3.95);
  mono(s, "CONTRACT  ·  CARD-D01  ·  10 KEYS  ·  7 SHOWN", M + 0.33, 2.58, 6.9, { fs: 10, color: COLORS.teal, charSpacing: 1.2 });
  rule(s, M + 0.33, 2.82, 6.9, COLORS.line, 0.75);
  const kv = [
    ["case_id", "CARD-D01"],
    ["classification", "unauthorized"],
    ["routing", "ready_for_review"],
    ["facts", "TX-D01  ·  117 XCR  ·  2026-10-01"],
    ["policy_ids", "CARD-POLICY-V2  ·  CARD-PROCEDURE-01"],
    ["deadline", "2026-10-31"],
    ["citations", "6 claims from 5 sources"],
  ];
  kv.forEach((r, i) => {
    const y = 2.96 + i * 0.36;
    mono(s, r[0], M + 0.33, y, 1.75, { fs: 10, color: COLORS.muted });
    mono(s, r[1], M + 2.1, y, 5.1, { fs: 11, color: COLORS.ink });
  });
  rule(s, M + 0.33, 5.62, 6.9, COLORS.line, 0.75);
  mono(s, "citation[0]  claim customer_evidence  source intake", M + 0.33, 5.72, 6.9, { fs: 10, color: COLORS.ink2 });
  mono(s, "citation[3]  claim transaction_record  source transactions", M + 0.33, 5.96, 6.9, { fs: 10, color: COLORS.ink2 });
  const rx = 8.55;
  mono(s, "ONE GATE", rx, 2.5, 4.0, { fs: 10, color: COLORS.teal, charSpacing: 1.2 });
  const gate = [
    ["sha256 of the draft", ["af65f686...ebd4"]],
    ["A human approves", ["201 pending review"]],
    ["One record or none", ["changed draft: refused, no write", "409 duplicate_case"]],
  ];
  gate.forEach((g, i) => {
    const y = 2.7 + i * 0.78;
    para(s, g[0], rx, y, 4.1, { fs: 18, font: FONT.head, color: COLORS.ink, h: 0.34 });
    g[1].forEach((m, j) => mono(s, m, rx, y + 0.36 + j * 0.24, 4.1, { fs: 10, color: COLORS.ink2 }));
  });
  para(s, "A stop is an outcome, not an error: the contract prints the reason and no record is written.",
    M, 6.55, 12.09, { fs: 13.5, color: COLORS.ink2 });
  notes(s, "Here is the object the pipeline produces. Ten keys, fixed before any prose exists: classification, route, facts from the transaction record, the deadline counted from the reported date, and six citations. The hash is what a human approves. If a field changes after approval, the runner refuses the draft before it sends anything, so no write is ever attempted. That refusal is the gate working.");
}

function s04_demo(pres) {
  const s = pres.addSlide();
  s.background = { color: COLORS.paper };
  chrome(s, 4, TOTAL, "03 · DEMO");
  headline(s, "Five complaints. Five ways it can go wrong.", { y: 1.1, w: 12.0, h: 0.7 });
  para(s, "Each row is a case you can run in the terminal. Every row now passes on main.", M, 1.88, 12.0, { fs: 15, color: COLORS.ink });
  headerRow(s, 2.3, [
    { t: "CASE", x: M, w: 1.0 },
    { t: "WHAT IT SHOULD DO", x: 1.72, w: 2.9 },
    { t: "WHAT YOU SEE", x: 4.75, w: 5.0 },
    { t: "STATUS", x: 10.6, w: 2.11, align: "right" },
  ]);
  const rows = [
    ["D01", "Record from the draft.", "Hash bound, approved, record written: 201, then a 200 replay. A changed draft stops before any write; 409 on a second record.", "ON MAIN", "green"],
    ["D05", "Decide a contradiction.", "Both contradictory sources cited; route manual_review, no deadline. A decided outcome, not a guess.", "ON MAIN", "green"],
    ["D08", "Refuse an instruction.", "The instruction sentence is filtered, never read as the customer's account.", "ON MAIN", "green"],
    ["D10", "Retry a fault.", "One injected transaction failure. The ladder retries once: 3 attempts, 1 retry, 1.3 s.", "ON MAIN", "green"],
    ["D09", "Refuse a redelivery.", "Duplicate of D02: TX-D02, 134 XCR, 16 Nov. The excerpt join runs on main.", "ON MAIN", "green"],
  ];
  rows.forEach((r, i) => {
    const y = 2.62 + i * 0.78;
    rule(s, M, y, 12.09, COLORS.line, 0.75);
    chip(s, r[0], M, y + 0.18, { w: 0.92, h: 0.27 });
    para(s, r[1], 1.72, y + 0.14, 2.9, { fs: 15, font: FONT.head, color: COLORS.ink, ls: 1.05 });
    para(s, r[2], 4.75, y + 0.17, 5.4, { fs: 12.5, ls: 1.2 });
    mono(s, r[3], 10.6, y + 0.2, 2.11, { fs: 10, align: "right", color: COLORS[r[4]], charSpacing: 1.1 });
  });
  rule(s, M, 6.38, 12.09, COLORS.line, 0.75);
  mono(s, "ON MAIN = on 8553bb3 today: every row is a passing dev case.", M, 6.46, 12.09,
    { fs: 10, color: COLORS.muted });
  mono(s, "THE DEMO RUNS IN THE TERMINAL AND THE MOCK BANK, NOT IN THIS DECK.", M, 6.68, 12.09,
    { fs: 10, color: COLORS.muted, charSpacing: 1.2 });
  notes(s, "Five cases, five outcomes, all on main. D01 walks the gate: draft, approval bound to the hash, a changed draft stopped before any write, and 409 on a second record. D05 and D06 decide a contradiction by routing to manual review and citing both sources. D10 exercises the retry ladder on an injected 503: three attempts, one retry, a draft in 1.3 seconds. D09 is a redelivery of D02 and is deduplicated. D08 stores the instruction-shaped note as evidence and never obeys it.");
}

function s05_evidence(pres) {
  const s = pres.addSlide();
  s.background = { color: COLORS.paper };
  chrome(s, 5, TOTAL, "04 · EVIDENCE");
  headline(s, "What is proven today.", { y: 1.1, w: 9.0, h: 0.7 });
  para(s, "Measured on origin/main 8553bb3 on 28 October, against the 12 dev cases.", M, 1.88, 11.5, { fs: 15, color: COLORS.ink });
  const cells = [
    ["12/12", "DEV CASES PASS", "0 format errors. 0 exceptions."],
    ["1014", "TESTS PASS", "100.00% of 3404. Gate is 100."],
    ["3670", "P95 DRAFT BUILD, MS", "p50 is 31 ms. D07 retries twice."],
    ["27", "TOOL ATTEMPTS", "24 first reads plus 3 retries."],
    ["0", "MODEL CALLS", "0.00 USD per pass. 12 of 12 rows."],
    ["126", "SUITE, SECONDS", "Full gate, this laptop."],
  ];
  cells.forEach((c, i) => {
    const x = 0.62 + (i % 3) * 4.13;
    const y = 2.35 + Math.floor(i / 3) * 1.72;
    rule(s, x, y, 3.85, COLORS.line, 0.75);
    text(s, c[0], { x, y: y + 0.1, w: 3.8, h: 0.86, fontFace: FONT.head, fontSize: 50, color: COLORS.ink, lineSpacingMultiple: 0.9 });
    mono(s, c[1], x, y + 1.02, 3.85, { fs: 10, color: COLORS.teal, charSpacing: 1.2 });
    para(s, c[2], x, y + 1.22, 3.85, { fs: 12.5 });
  });
  para(s, "Twelve of twelve build. Manual review and retries are decisions, and none of them fails silently.", M, 5.95, 11.5, { fs: 15, color: COLORS.ink });
  mono(s, "ALL TWELVE PASS  ·  0 EXCEPTIONS  ·  0 MODEL CALLS  ·  0.00 USD  ·  D07 4 ATTEMPTS, D10 3",
    M, 6.45, 12.09, { fs: 10, color: COLORS.muted, charSpacing: 1.1 });
  notes(s, "These are the numbers at 8553bb3. 1014 tests pass and coverage is 100 percent of 3404 statements, and the gate fails the build below that. All twelve dev cases build a contract with zero format errors and zero exceptions. Draft assembly takes 3670 milliseconds at p95, driven by the two retried cases, and 31 milliseconds at p50. The run makes zero model calls, and D07 and D10 exercise the retry ladder instead of stopping.");
}

function s06_architecture(pres) {
  const s = pres.addSlide();
  s.background = { color: COLORS.paper };
  chrome(s, 6, TOTAL, "05 · ARCHITECTURE");
  headline(s, "Deterministic by design.\nThe model sits outside the decision path.", { y: 1.05, w: 11.0, h: 1.36 });
  para(s, "Untrusted text enters at the left. A human opens the last door. Nothing in between asks a model.",
    M, 2.44, 11.6, { fs: 15, color: COLORS.ink });
  s.addImage({ path: ASSET("pipeline_bare.png"), x: M, y: 2.86, w: 12.09, h: 2.826 });
  rule(s, M, 5.92, 12.09, COLORS.line, 0.75);
  const g = [
    ["ONE CONTRACT PER CASE", "Ten keys, one object, written by code."],
    ["A STOP CARRIES A REASON", "Two typed exceptions print the case and the source."],
    ["EVERY CITATION IS AN EXACT SLICE", "A quote that is not in the source is refused."],
  ];
  g.forEach((r, i) => {
    const x = 0.62 + i * 4.13;
    mono(s, r[0], x, 6.0, 3.85, { fs: 10, color: COLORS.teal, charSpacing: 1.1 });
    para(s, r[1], x, 6.2, 3.85, { fs: 12.5 });
  });
  notes(s, "Read the figure left to right. Untrusted documents become typed bodies, the core turns them into one contract with six exact citations, and the last door is a person holding a hash. The model is not in this lane, and not in the fail path either: two typed exceptions stop an unbuildable case and print a reason. Nothing dashed on this page is a promise.");
}

function s07_model(pres) {
  const s = pres.addSlide();
  s.background = { color: COLORS.paper };
  chrome(s, 7, TOTAL, "06 · THE MODEL");
  headline(s, "Once approved, the model answers\ntwo closed questions. Nothing else.", { y: 1.05, w: 10.6, h: 1.34 });
  card(s, M, 2.5, 5.6, 2.35, COLORS.card, COLORS.line);
  mono(s, "TEMPLATE PATH  ·  ON MAIN", M + 0.3, 2.66, 5.0, { fs: 10, color: COLORS.teal, charSpacing: 1.1 });
  para(s, "Frozen facts, fixed sentences.", M + 0.3, 2.9, 5.0, { fs: 17, font: FONT.head, color: COLORS.ink, h: 0.42 });
  para(s, "Every sentence is a function of the contract. The meter shows 0 model calls, 0 tokens and 0.00 USD per pass.",
    M + 0.3, 3.42, 5.0, { fs: 13 });
  card(s, 6.88, 2.5, 5.83, 2.35, COLORS.card, COLORS.line);
  mono(s, "MODEL PATH  ·  ADR-003  ·  MERGED, OFF BY DEFAULT", 7.18, 2.66, 5.2, { fs: 10, color: COLORS.amber, charSpacing: 1.1 });
  para(s, "Two closed answers, inside the boundary.", 7.18, 2.9, 5.42, { fs: 17, font: FONT.head, color: COLORS.ink, h: 0.42 });
  para(s, "Merged and off by default. It would answer two closed questions after the facts freeze. Cost and latency at volume: not measured. No live model run is approved.",
    7.18, 3.42, 5.25, { fs: 13 });
  s.addShape("rect", { x: M, y: 5.24, w: 12.09, h: 0.98, fill: { color: COLORS.sand }, line: { color: COLORS.line, width: 0.75 } });
  para(s, "If the facts are frozen before the model speaks, a bad sentence cannot move a classification, a deadline, or a citation.",
    0.95, 5.38, 11.4, { fs: 16, font: FONT.head, italic: true, color: COLORS.ink, ls: 1.2 });
  mono(s, "ADR-001 ACCEPTED 25 OCT 2026: A MODEL MAY WRITE PROSE ONLY. FACTS, ROUTE, DEADLINE AND CITATIONS COME FROM CODE.",
    M, 6.55, 12.09, { fs: 10, color: COLORS.muted, charSpacing: 1.1 });
  notes(s, "Two paths, drawn apart on purpose. The path on main is a template: every sentence is a function of frozen facts, which is why the meter shows zero model calls. The second path in ADR-003 is merged and off by default: a model may answer two closed questions after the facts freeze. No live run has been approved, so nothing here shows cost or latency at volume.");
}

function s08_trust(pres) {
  const s = pres.addSlide();
  s.background = { color: COLORS.paper };
  chrome(s, 8, TOTAL, "07 · TRUST");
  headline(s, "Untrusted text is read, never obeyed.", { y: 1.08, w: 12.0, h: 0.72 });
  para(s, "The merchant writes an instruction. It is stored as data, not among the six citations.",
    M, 1.84, 11.8, { fs: 15, color: COLORS.ink });
  s.addImage({ path: ASSET("boundary_bare.png"), x: M, y: 2.28, w: 12.09, h: 4.524 });
  notes(s, "This is the boundary slide. The merchant note for D08 is written as an instruction: ignore policy, promise a refund, copy the tokens. The system stores it as evidence and quotes nothing from it as an order. The note is not among D08's citations. src/untrusted.py holds the instruction filter and the restricted-value redaction, and every read path imports it. contract.py:182 defines the pattern and line 881 applies it while deciding whether a duplicate was reported. Merchant text still has no route into classification.");
}

function s09_limits(pres) {
  const s = pres.addSlide();
  s.background = { color: COLORS.paper };
  chrome(s, 9, TOTAL, "08 · LIMITS");
  headline(s, "What is not done, and why.", { y: 1.1, w: 12.0, h: 0.7 });
  para(s, "One delivered band, four named gaps, and a short not-attempted list.", M, 1.88, 10.5, { fs: 15, color: COLORS.ink });
  mono(s, "ON MAIN  ·  12 OF 12 DEV CASES", M, 2.3, 6.0, { fs: 10, color: COLORS.teal, charSpacing: 1.2 });
  para(s, "Every case builds. D05 and D06 route to manual review, D07 and D10 retry, D09 deduplicates. The review gate, the changed-draft refusal, the 409 and the record write are wired.",
    M, 2.52, 11.6, { fs: 13 });
  s.addShape("rect", { x: M, y: 3.05, w: 12.09, h: 2.4, fill: { color: COLORS.sand }, line: { color: COLORS.line, width: 0.75 } });
  mono(s, "NOT DELIVERED  ·  FOUR NAMED GAPS", M + 0.33, 3.24, 8.0,
    { fs: 10, color: COLORS.amber, charSpacing: 1.2 });
  const gaps = [
    ["REVIEWER IDENTITY", "The gate binds a draft to a hash, not to a person. M1, not started."],
    ["LIVE MODEL ROUTE", "ADR-003 is merged and off by default. No approved live run, no measured cost."],
    ["UPDATE AND CLOSE", "Blocked by Gate U (L1). Only create is wired."],
    ["WRAPPED STATEMENT", "The customer statement has no line limit (docs/RED_TEAM.md:52)."],
  ];
  gaps.forEach((r, i) => {
    const y = 3.56 + i * 0.42;
    mono(s, r[0], M + 0.33, y, 2.4, { fs: 10, color: COLORS.ink, charSpacing: 0.6 });
    para(s, r[1], M + 2.85, y - 0.02, 8.7, { fs: 12, h: 0.24 });
  });
  mono(s, "NOT ATTEMPTED", M, 5.66, 6.0, { fs: 10, color: COLORS.muted, charSpacing: 1.2 });
  para(s, "A user interface. OCR. Production identity. Adjudication of a cut-off.",
    M, 5.9, 11.6, { fs: 13, h: 0.22 });
  para(s, "Shape as shipped: single node, SQLite, no reviewer identity.",
    M, 6.18, 11.6, { fs: 13, h: 0.22 });
  mono(s, "DO NOT COUNT A GAP AS DELIVERED.", M, 6.62, 12.09,
    { fs: 10, color: COLORS.red, charSpacing: 1.2 });
  notes(s, "One delivered band and one gap list. On main: all twelve cases, the record, the changed-draft refusal and the 409, and a wired retry ladder. The gaps are named: reviewer identity is not started, the model route is merged but off with no approved live run, update and close are blocked by Gate U, and the wrapped statement has no line limit. Not attempted: a user interface, OCR, production identity, adjudication, and the deployment shape, which is one node, SQLite, and no reviewer identity.");
}

function s10_operations(pres) {
  const s = pres.addSlide();
  s.background = { color: COLORS.paper };
  chrome(s, 10, TOTAL, "09 · OPERATIONS");
  headline(s, "It fails in daylight.", { y: 1.1, w: 10.0, h: 0.7 });
  para(s, "Every stop is a typed exception with a printed reason. Every run leaves a meter line and audit rows.",
    M, 1.88, 11.6, { fs: 15, color: COLORS.ink });
  const rows = [
    ["A STOP CARRIES A REASON", "BankReadError and ContractError name the case and the source, and write nothing."],
    ["ONE METER LINE PER CASE", "Path, duration, model calls, tokens, cost. No case text is written to the meter."],
    ["FIVE AUDIT ROWS", "Two tool reads, review requested, human approved, record created. Walked for D01."],
    ["HEALTH AND RESET", "The runbook names the endpoint and the reset step for the mock bank."],
  ];
  rows.forEach((r, i) => {
    const y = 2.4 + i * 0.86;
    rule(s, M, y, 6.2, COLORS.line, 0.75);
    mono(s, r[0], M, y + 0.1, 6.2, { fs: 10, color: COLORS.teal, charSpacing: 1.2 });
    para(s, r[1], M, y + 0.32, 6.15, { fs: 13 });
  });
  s.addShape("rect", { x: 7.05, y: 2.3, w: 5.66, h: 2.95, fill: { color: COLORS.navy }, line: { color: COLORS.navy, width: 0.75 } });
  const code = [
    "GET  /v1/cases            200",
    "POST /v1/reviews          201 pending",
    "POST same key             200 replay",
    "changed field             refused",
    "   before any POST: nothing written",
    "second record             409 duplicate_case",
  ];
  code.forEach((c, i) => {
    text(s, c, { x: 7.3, y: 2.5 + i * 0.36, w: 5.2, h: 0.3, fontFace: FONT.mono, fontSize: 10.5,
      color: i === 4 ? COLORS.tealLight : COLORS.cream, margin: 0, valign: "top" });
  });
  s.addShape("rect", { x: 7.05, y: 5.42, w: 5.66, h: 0.98, fill: { color: COLORS.sand }, line: { color: COLORS.line, width: 0.75 } });
  mono(s, "RETRY LADDER: 3 ATTEMPTS, WAITS OF 1 S THEN 2 S.", 7.3, 5.56, 5.2, { fs: 10, color: COLORS.ink2 });
  mono(s, "WIRED THROUGH TOOL RETRY: D07 4 ATTEMPTS, D10 3.", 7.3, 5.86, 5.2, { fs: 10, color: COLORS.tealLight });
  mono(s, "THE SCORED RUN EXERCISES IT: 3 RETRIES, 0 STOPS.", M, 6.55, 12.09,
    { fs: 10, color: COLORS.muted, charSpacing: 1.1 });
  notes(s, "Failure is designed to be visible. A bank read that fails raises a typed error; a 5xx is retried by the ladder, and a case that cannot be built stops with the case and the source named. Every run writes one meter line per case, and five audit rows for the hand-walked D01. D07 needs four attempts and D10 needs three in the scored run, so the ladder has real callers.");
}

function s11_roadmap(pres) {
  const s = pres.addSlide();
  s.background = { color: COLORS.paper };
  chrome(s, 11, TOTAL, "10 · ROADMAP");
  headline(s, "The next 30 days, in order.", { y: 1.1, w: 12.0, h: 0.7 });
  para(s, "Five moves, ordered so each one unblocks the next.", M, 1.88, 10.5, { fs: 15, color: COLORS.ink });
  const rows = [
    ["01", "Add reviewer identity.", "The gate binds a draft to a hash, not to a person. M1, not started.", "NEXT"],
    ["02", "Approve the model route with measured cost.", "ADR-003 is merged and off. Needs a volume run before anyone quotes latency or price.", "AFTER"],
    ["03", "Start a real intake pilot with two analysts.", "Thirty days, real complaints, the same contract and the same gate.", "PILOT"],
    ["04", "Name the next two complaint types.", "The contract generalises only as far as the policy set does.", "THEN"],
    ["05", "Enforce the rulesets, or drop them.", "The GitHub plan returns 403, so the review rules stay unenforced.", "BLOCKED"],
  ];
  rows.forEach((r, i) => {
    const y = 2.36 + i * 0.78;
    rule(s, M, y, 12.09, COLORS.line, 0.75);
    text(s, r[0], { x: M, y: y + 0.04, w: 0.8, h: 0.5, fontFace: FONT.head, fontSize: 26, color: COLORS.line2, margin: 0, valign: "top" });
    para(s, r[1], 1.55, y + 0.1, 7.6, { fs: 16, font: FONT.head, color: COLORS.ink, ls: 1.05, h: 0.3 });
    para(s, r[2], 1.55, y + 0.44, 10.3, { fs: 12.5, h: 0.24 });
    mono(s, r[3], 10.5, y + 0.14, 2.21, { fs: 10, align: "right", color: COLORS.teal, charSpacing: 1.1 });
  });
  rule(s, M, 6.38, 12.09, COLORS.line, 0.75);
  mono(s, "LATER: PRODUCTION DEPLOYMENT, THEN ADJUDICATION OF A CUT-OFF.", M, 6.48, 12.09,
    { fs: 10, color: COLORS.muted, charSpacing: 1.2 });
  notes(s, "Five moves, in dependency order. Reviewer identity comes first because the gate binds a hash, not a person. The model route needs a measured volume run before anyone quotes a number. Then the pilot with two analysts, then the next complaint types, which the contract can only absorb as far as the policy set goes. Rulesets stay unenforced until the GitHub plan allows them.");
}

function s12_pod(pres) {
  const s = pres.addSlide();
  s.background = { color: COLORS.paper };
  chrome(s, 12, TOTAL, "11 · THE POD");
  headline(s, "Three people, one system,\ndefended line by line.", { y: 1.05, w: 11.8, h: 1.34 });
  para(s, "We built one path and three seams: the gate, the escalation, the retry.", M, 2.36, 11.5, { fs: 15, color: COLORS.ink });
  const cols = [
    ["Kanit", "GATE AND EVIDENCE", "Idempotency. The approval bound to the draft hash, a changed draft stopped before any write, 409 live, and the evidence pack behind every number here.", "ASK KANIT", "What stops a changed draft from being written?"],
    ["Mani", "ESCALATION", "Merged in 52. A follow-up that contradicts the intake routes to manual review with both sources cited. That is D05 and D06.", "ASK MANI", "What happens when a follow-up names a document the read step cannot load?"],
    ["Zach", "RESILIENCE", "Retry and breaker around every tool read: merged and wired. D07 and D10 exercise the ladder in the scored run.", "ASK ZACH", "Why three attempts, and waits of one second then two?"],
  ];
  cols.forEach((c, i) => {
    const x = 0.62 + i * 4.13;
    rule(s, x, 2.82, 3.78, COLORS.line2, 1);
    para(s, c[0], x, 2.94, 3.78, { fs: 24, font: FONT.head, color: COLORS.ink, h: 0.5 });
    mono(s, c[1], x, 3.5, 3.78, { fs: 10, color: COLORS.teal, charSpacing: 1.2 });
    para(s, c[2], x, 3.74, 3.6, { fs: 13.5 });
    rule(s, x, 5.1, 3.78, COLORS.line, 0.75);
    mono(s, c[3], x, 5.2, 3.78, { fs: 10, color: COLORS.muted, charSpacing: 1.1 });
    para(s, c[4], x, 5.42, 3.62, { fs: 15, font: FONT.head, color: COLORS.ink, ls: 1.15 });
  });
  mono(s, "ONE REPO, ONE GATE  ·  1014 TESTS  ·  100.00% OF 3404 STATEMENTS  ·  0 OPEN PULL REQUESTS", M, 6.55, 12.09,
    { fs: 10, color: COLORS.muted, charSpacing: 1.1 });
  notes(s, "Three people built one path. The gate is mine: idempotency, the approval bound to the draft hash, and the evidence pack behind every number here. Mani owns escalation, merged in 52, which is the D05 and D06 cases. Zach owns resilience: the ladder is merged and wired, and D07 and D10 exercise it. The three questions at the bottom are the ones to expect, and each of us answers one.");
}

function s13_close(pres) {
  const s = pres.addSlide();
  s.background = { color: COLORS.navy };
  text(s, "THE ASK", { x: 0.9, y: 0.9, w: 6, h: 0.22, fontFace: FONT.mono, fontSize: 10.5,
    color: COLORS.tealLight, charSpacing: 1.4 });
  text(s, "The gate is the product.", { x: 0.9, y: 1.4, w: 10.2, h: 1.06, fontFace: FONT.head,
    fontSize: 54, color: COLORS.cream, lineSpacingMultiple: 0.98 });
  const asks = [
    ["01", "Approve the model route for two closed questions."],
    ["02", "Name the next two complaint types."],
    ["03", "Two analysts for a 30 day intake pilot."],
  ];
  asks.forEach((a, i) => {
    const y = 3.2 + i * 0.8;
    mono(s, a[0], 0.9, y + 0.08, 0.5, { fs: 10, color: COLORS.tealLight });
    para(s, a[1], 1.6, y, 8.6, { fs: 20, font: FONT.head, color: COLORS.cream, ls: 1.1 });
  });
  para(s, "Analyst minutes are not measured, so none are claimed. The pilot's first output is that number.",
    2.97, 5.2, 9.4, { fs: 12, color: COLORS.tealLight, ls: 1.2 });
  rule(s, 0.9, 5.95, 4.2, "1E3A44", 1);
  mono(s, "THANK YOU. QUESTIONS, INCLUDING THE HARD ONES.", 0.9, 6.12, 7.6, { fs: 10, color: "9DB0B4", charSpacing: 1.2 });
  s.addImage({ path: ASSET("motif_alpha.png"), x: 10.6, y: 4.3, w: 2.2, h: 2.2 });
  mono(s, "[ 13 / 16 ]", 11.0, 6.9, 1.71, { fs: 10, color: "6E8388", align: "right" });
  notes(s, "The ask is three things. Approve the model route for the two closed questions, so prose can move without touching a classification. Name the next two complaint types, because the contract generalises only as far as the policy set does. Give two analysts thirty days of real intake. Nothing here claims a saved minute: analyst minutes are not measured, so none are claimed, and the pilot's first output is that number.");
}

function a1_contract(pres) {
  const s = pres.addSlide();
  s.background = { color: COLORS.paper };
  chrome(s, 14, TOTAL, "APPENDIX A1 · THE CONTRACT");
  headline(s, "One contract, field by field.", { y: 1.1, w: 11.0, h: 0.7 });
  para(s, "The shape of the object. Citations, missing_information and follow_up_questions are abbreviated.", M, 1.88, 11.6, { fs: 15, color: COLORS.ink });
  card(s, M, 2.35, 8.0, 3.9);
  chip(s, "PSEUDO-JSON · SHAPE ONLY", 6.15, 2.42, { w: 2.42, h: 0.26 });
  const json = [
    "{",
    "  \"case_id\": \"CARD-D01\",",
    "  \"classification\": \"unauthorized\",",
    "  \"routing\": \"ready_for_review\",",
    "  \"policy_ids\": [\"CARD-POLICY-V2\", \"CARD-PROCEDURE-01\"],",
    "  \"facts\": { \"transaction_id\": \"TX-D01\", \"amount\": 117,",
    "             \"currency\": \"XCR\", \"reported_date\": \"2026-10-01\" },",
    "  \"deadline\": \"2026-10-31\",",
    "  \"citations\": [ 6 claims, 5 source ids ],",
    "  \"narrative\": \"one paragraph, template on main\"",
    "}",
  ];
  json.forEach((l, i) => {
    text(s, l, { x: 0.95, y: 2.72 + i * 0.31, w: 7.3, h: 0.26, fontFace: FONT.mono, fontSize: 11,
      color: l.indexOf("\"") > 2 ? COLORS.ink : COLORS.ink2, margin: 0, valign: "top" });
  });
  const callouts = [
    ["FACTS", "Transaction id, amount, currency and reported date come from the transaction record."],
    ["DEADLINE", "Counted from the reported date under policy version 2."],
    ["CITATIONS", "Six claims, five source ids. Each quote is an exact slice."],
    ["NARRATIVE", "The only free text. On main it is a template."],
  ];
  callouts.forEach((c, i) => {
    const y = 2.4 + i * 1.0;
    mono(s, c[0], 9.0, y, 3.7, { fs: 10, color: COLORS.teal, charSpacing: 1.2 });
    para(s, c[1], 9.0, y + 0.2, 3.7, { fs: 12.5 });
  });
  notes(s, "One contract, field by field, the shape of the object for D01. Facts come from the transaction record, not from the intake text. The deadline is counted from the reported date under policy version two. Citations are six claims, each tied to a source id and an exact slice. The panel is pseudo-JSON: citations, missing_information and follow_up_questions are abbreviated, and the narrative on main is a template.");
}

function a2_cases(pres) {
  const s = pres.addSlide();
  s.background = { color: COLORS.paper };
  chrome(s, 15, TOTAL, "APPENDIX A2 · THE TWELVE DEV CASES");
  headline(s, "Twelve cases, twelve contracts, zero stops.", { y: 1.1, w: 12.09, size: 32, h: 0.72 });
  headerRow(s, 2.0, [
    { t: "CASE", x: M, w: 1.0 },
    { t: "CITES", x: 1.65, w: 1.2 },
    { t: "RESULT", x: 3.05, w: 1.2 },
    { t: "REASON", x: 4.45, w: 8.2 },
  ]);
  const rows = [
    ["D01", "6", "PASS", "contract, review requested, record written"],
    ["D02", "7", "PASS", "duplicate charge, deadline 16 Nov"],
    ["D03", "6", "PASS", "service not received, deadline 2 Dec"],
    ["D04", "6", "PASS", "unauthorized, request information"],
    ["D05", "9", "PASS", "ambiguous, manual review, both sources cited"],
    ["D06", "8", "PASS", "unsupported, manual review, no deadline"],
    ["D07", "7", "PASS", "4 attempts, 2 retries, 3.7 s"],
    ["D08", "7", "PASS", "instruction-shaped note stored as data, not cited"],
    ["D09", "7", "PASS", "duplicate of D02: TX-D02, 134 XCR"],
    ["D10", "6", "PASS", "3 attempts, 1 retry, 1.3 s"],
    ["D11", "6", "PASS", "reads CARD-POLICY-V1, deadline 20 Sep"],
    ["D12", "6", "PASS", "service not received, request information"],
  ];
  rows.forEach((r, i) => {
    const y = 2.34 + i * 0.33;
    mono(s, r[0], M, y, 1.0, { fs: 10, color: COLORS.ink });
    mono(s, r[1], 1.65, y, 1.2, { fs: 10, color: COLORS.amber });
    mono(s, r[2], 3.05, y, 1.2, { fs: 10, color: r[2] === "PASS" ? COLORS.green : COLORS.red });
    mono(s, r[3], 4.45, y, 8.2, { fs: 10, color: COLORS.ink2 });
  });
  mono(s, "SCORED RUN AT 8C3AC7F, 28 OCT 2026  ·  12 / 12 PASS, 0 EXCEPTIONS", M, 6.5, 12.09,
    { fs: 10, color: COLORS.muted, charSpacing: 1.1 });
  notes(s, "The twelve dev cases at a glance. All twelve build a contract. Five are not a plain happy path: D05 and D06 are manual-review decisions that cite the contradiction, D07 and D10 retry through injected failures, and D09 is deduplicated against D02. Nothing here is a silent failure.");
}

function a3_sources(pres) {
  const s = pres.addSlide();
  s.background = { color: COLORS.paper };
  chrome(s, 16, TOTAL, "APPENDIX A3 · SOURCES AND COMMANDS");
  headline(s, "Where every number comes from.", { y: 1.1, w: 11.0, h: 0.7 });
  para(s, "Read at origin/main 8553bb3 in the worktree .worktrees/lane-deck.", M, 1.88, 11.6, { fs: 15, color: COLORS.ink });
  const files = [
    ["src/contract.py", "1149 lines. Assembly and citations."],
    ["src/contract_records.py", "561 lines. Contract and meter per case."],
    ["src/review_gate.py", "227 lines. Draft hash, 403, 409."],
    ["src/untrusted.py", "220 lines. Evidence, never instructions."],
    ["src/resilience.py", "192 lines. The ladder, wired."],
    ["tools/runtime.py", "Mock bank and the approval gate."],
    ["tools/scored_run.py", "The 12 cases and the report."],
    ["docs/deck/FACTS.md", "The number sheet behind every figure."],
  ];
  files.forEach((r, i) => {
    const x = M + (i % 2) * 6.05;
    const y = 2.24 + Math.floor(i / 2) * 0.62;
    mono(s, r[0], x, y, 5.6, { fs: 10.5, color: COLORS.ink });
    para(s, r[1], x, y + 0.24, 5.5, { fs: 12.5, h: 0.22 });
  });
  card(s, M, 4.8, 12.09, 1.36, COLORS.navy, COLORS.navy);
  mono(s, "NUMBERS  ·  FROM .WORKTREES/DECK-MAIN", M + 0.24, 4.9, 7.2, { fs: 10, color: COLORS.tealLight, charSpacing: 1.1 });
  text(s, "python -m tools.runtime serve --data data/dev --state .state/mock.sqlite3 --port 8899",
    { x: M + 0.24, y: 5.12, w: 11.6, h: 0.24, fontFace: FONT.mono, fontSize: 10, color: COLORS.cream, margin: 0, valign: "top" });
  text(s, ".venv/Scripts/python.exe -m pytest -q",
    { x: M + 0.24, y: 5.34, w: 11.6, h: 0.24, fontFace: FONT.mono, fontSize: 10, color: COLORS.cream, margin: 0, valign: "top" });
  mono(s, "SCORED RUN  ·  SAME WORKTREE", M + 0.24, 5.6, 4.4, { fs: 10, color: COLORS.tealLight, charSpacing: 1.1 });
  mono(s, "DECK  ·  FROM THE REPO ROOT", 6.4, 5.6, 4.4, { fs: 10, color: COLORS.tealLight, charSpacing: 1.1 });
  text(s, "python tools/scored_run.py --base-url http://127.0.0.1:8899",
    { x: M + 0.24, y: 5.82, w: 5.4, h: 0.24, fontFace: FONT.mono, fontSize: 10, color: COLORS.cream, margin: 0, valign: "top" });
  text(s, "bash docs/deck/build/build.sh",
    { x: 6.4, y: 5.82, w: 5.6, h: 0.24, fontFace: FONT.mono, fontSize: 10, color: COLORS.cream, margin: 0, valign: "top" });
  mono(s, "The venv runs the suite; the mock serves the scored run.", M, 6.36, 12.09, { fs: 10, color: COLORS.muted });
  mono(s, "RERUN THE SCORED RUN BEFORE QUOTING ANY NUMBER FROM THIS PAGE.", M, 6.6, 12.09,
    { fs: 10, color: COLORS.muted, charSpacing: 1.1 });
  notes(s, "Sources and commands, so anyone can reproduce this. Every number in the deck comes from these files at 8553bb3. The mock serves on 8899, the scored run points at it, and the venv runs the suite. One command, python -m src.run_loop, starts the mock, scores the twelve cases and stops the mock. The deck rebuilds from the repo root. If a number looks wrong, rerun the scored run or the one-command loop and check the meter file.");
}

// ---- assemble ------------------------------------------------------------
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.title = "Lumen Bank dispute copilot, final demo and technical defense";
pres.author = "Kanit, Mani, Zach";
pres.company = "Coforge";
[s01_cover, s02_problem, s03_product, s04_demo, s05_evidence, s06_architecture, s07_model,
 s08_trust, s09_limits, s10_operations, s11_roadmap, s12_pod, s13_close, a1_contract, a2_cases, a3_sources]
  .forEach((fn) => fn(pres));

pres.writeFile({ fileName: OUT }).then(() => console.log("wrote " + OUT));
