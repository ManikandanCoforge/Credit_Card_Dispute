// docs/deck/build/theme.js — shared tokens and chrome for the Lumen deck.
// Extends the print system in docs/status/project-status-2026-10-26.html and docs/flow/out/p1@2x.png.
const COLORS = {
  paper: "FBFAF7", card: "FFFFFF", sand: "F3EFE6", line: "E2DDD2", line2: "D3CDC0",
  ink: "12262E", ink2: "2B454F", muted: "68777D",
  teal: "0D6F6A", tealSoft: "E6F2EF", green: "1C7A58", amber: "A96900", red: "B4452F",
  navy: "0A1C24", cream: "F4EFE3", tealLight: "7FBDB4",
};
const FONT = { head: "Georgia", body: "Segoe UI", mono: "Consolas" };
const W = 13.333, H = 7.5, M = 0.62;
const FOOTER = "Final demo and technical defense \u00b7 29 October 2026";

const text = (s, str, o) => s.addText(str, Object.assign({
  x: M, y: 1.28, w: W - 2 * M, h: 0.4, fontFace: FONT.body, fontSize: 13.5,
  color: COLORS.ink2, margin: 0, valign: "top", lineSpacingMultiple: 1.18,
}, o));

const rule = (s, x, y, w, color = COLORS.line, width = 0.75) =>
  s.addShape("line", { x, y, w, h: 0, line: { color, width } });

// Chrome: hairline + kicker row + footer. num is 1-based.
function chrome(s, num, total, kicker) {
  rule(s, M, 0.62, W - 2 * M, COLORS.line2, 1);
  text(s, kicker || "", { x: M, y: 0.38, w: 6, h: 0.22, fontFace: FONT.mono, fontSize: 10,
    color: COLORS.teal, charSpacing: 1.2, valign: "middle" });
  text(s, "LUMEN BANK \u00b7 DISPUTE COPILOT", { x: W - M - 5, y: 0.38, w: 5, h: 0.22,
    fontFace: FONT.mono, fontSize: 10, color: COLORS.muted, align: "right", charSpacing: 1.2, valign: "middle" });
  rule(s, M, 6.98, W - 2 * M, COLORS.line, 0.75);
  text(s, FOOTER, { x: M, y: 7.08, w: 6, h: 0.24, fontFace: FONT.mono, fontSize: 10, color: COLORS.muted });
  text(s, "[ " + String(num).padStart(2, "0") + " / " + String(total).padStart(2, "0") + " ]",
    { x: W - M - 2.5, y: 7.08, w: 2.5, h: 0.24, fontFace: FONT.mono, fontSize: 10, color: COLORS.muted, align: "right" });
}

// Headline block: Georgia, tight leading, optional lede under it.
function headline(s, str, o) {
  o = o || {};
  const size = o.size || 34;
  const h = o.h || (size / 72) * 1.06 * (str.split("\n").length);
  text(s, str, { x: o.x || M, y: o.y || 1.12, w: o.w || (W - 2 * M), h,
    fontFace: FONT.head, fontSize: size, color: COLORS.ink, lineSpacingMultiple: 0.98 });
  return (o.y || 1.12) + h;
}

// Small-caps-ish mono label, the deck's main eyebrow.
function eyebrow(s, str, o) {
  o = o || {};
  text(s, str.toUpperCase(), { x: o.x || M, y: o.y || 0, w: o.w || 4, h: 0.2, fontFace: FONT.mono,
    fontSize: o.size || 10.5, color: o.color || COLORS.muted, charSpacing: 1.4 });
}

// Outlined chip, used for tags such as IN REVIEW / NOT ON MAIN.
function chip(s, str, x, y, o) {
  o = o || {};
  const w = o.w || Math.max(1.1, str.length * 0.088 + 0.28);
  s.addShape("roundRect", { x, y, w, h: o.h || 0.28, fill: { color: o.fill || COLORS.sand },
    line: { color: o.line || COLORS.line2, width: 0.75 }, rectRadius: 0.03 });
  text(s, str.toUpperCase(), { x, y, w, h: o.h || 0.28, fontFace: FONT.mono, fontSize: 10,
    color: o.color || COLORS.ink2, align: "center", valign: "middle", charSpacing: 0.8 });
}

module.exports = { COLORS, FONT, W, H, M, text, rule, chrome, headline, eyebrow, chip };
