#!/usr/bin/env node
// Build a print-grade A4 PDF from a Markdown source. Node 22+ (built-in WebSocket).
// Usage: node build.mjs <file.md> [--out <dir>]
// Front matter: title, subtitle, docid, version, status, date, owner, audience, classification, org, programme, stamp.
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname, basename, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);

const HERE = dirname(fileURLToPath(import.meta.url));
const CHROME_CANDIDATES = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
];
const CSS = readFileSync(join(HERE, "theme.css"), "utf8");

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function slug(s) {
  return String(s).toLowerCase().replace(/<[^>]+>/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}
function inline(s) {
  let t = esc(s);
  t = t.replace(/\x60([^\x60]+)\x60/g, function (_m, a) { return "<code>" + a + "</code>"; });
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
  t = t.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2">$1</a>');
  return t;
}
function parseFront(text) {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n/);
  if (!m) return [{}, text];
  const meta = {};
  for (const line of m[1].split(/\r?\n/)) {
    const kv = line.match(/^([A-Za-z_]+):\s*(.*)$/);
    if (kv) meta[kv[1]] = kv[2].replace(/^"(.*)"$/, "$1");
  }
  return [meta, text.slice(m[0].length)];
}
function splitRow(line) {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|")) s = s.slice(0, -1);
  return s.split(/(?<!\\)\|/).map(function (c) { return c.trim().replace(/\\\|/g, "|"); });
}
function isSep(line) {
  const t = line.trim();
  return t.includes("|") && splitRow(t).every(function (c) { return /^:?-{3,}:?$/.test(c); });
}
function mdToHtml(src, baseDir) {
  const lines = src.split(/\r?\n/);
  const path = require("node:path");
  function figureBlock(rel, caption) {
    try {
      const p = path.isAbsolute(rel) ? rel : path.resolve(baseDir || HERE, rel);
      let svg = readFileSync(p, "utf8");
      svg = svg.replace(/<\?xml[^>]*\?>/g, "").replace(/<!--[\s\S]*?-->/g, "");
      svg = svg.replace(/<svg([^>]*)>/, function (_m, attrs) {
        let a = attrs.replace(/\swidth="[^"]*"/, "").replace(/\sheight="[^"]*"/, "");
        if (!/preserveAspectRatio/.test(a)) a += ' preserveAspectRatio="xMidYMid meet"';
        return '<svg class="figsvg"' + a + ">";
      });
      return '<figure class="fig">' + svg + '<figcaption>' + inline(caption) + "</figcaption></figure>";
    } catch (e) {
      return '<p class="figerr">[figure missing: ' + esc(rel) + "]</p>";
    }
  }
  const out = [];
  const headings = [];
  let i = 0;
  let fence = null;
  let para = [];
  let listStack = [];
  function flushPara() {
    if (para.length) { out.push("<p>" + inline(para.join(" ").replace(/\s+/g, " ").trim()) + "</p>"); para = []; }
  }
  function closeLists() {
    while (listStack.length) out.push(listStack.pop() === "ul" ? "</ul>" : "</ol>");
  }
  while (i < lines.length) {
    const raw = lines[i];
    const line = raw.replace(/\s+$/, "");
    if (fence) {
      if (line.trim().startsWith(fence)) { out.push("</code></pre>"); fence = null; }
      else out.push(esc(raw));
      i++; continue;
    }
    const f = line.match(/^\s*(\x60{3,}|~{3,})\s*([\w+-]*)\s*$/);
    if (f) {
      flushPara(); closeLists();
      fence = f[1];
      out.push('<pre><code' + (f[2] ? ' class="language-' + esc(f[2]) + '"' : "") + ">");
      i++; continue;
    }
    if (!line.trim()) { flushPara(); i++; continue; }
    if (/^\[\[PAGEBREAK\]\]$/.test(line.trim())) { flushPara(); closeLists(); out.push('<div class="pb"></div>'); i++; continue; }
    const fig = line.trim().match(/^\[\[FIGURE:\s*(.+?)\s*\|\s*(.+?)\s*\]\]$/);
    if (fig) { flushPara(); closeLists(); out.push(figureBlock(fig[1], fig[2])); i++; continue; }
    if (/^\[\[TOC\]\]$/.test(line.trim())) { flushPara(); closeLists(); out.push("[[TOC]]"); i++; continue; }
    if (/^<!--.*-->$/.test(line.trim())) { i++; continue; }
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      flushPara(); closeLists();
      const depth = h[1].length;
      const text = h[2].trim();
      const id = slug(text);
      headings.push({ depth: depth, text: text, id: id });
      const mark = '<span class="hmark">[[H' + (headings.length - 1) + ']]</span>';
      out.push('<' + "h" + depth + ' id="' + id + '" class="h' + depth + '">' + mark + inline(text) + "</h" + depth + ">");
      i++; continue;
    }
    if (line.includes("|") && i + 1 < lines.length && isSep(lines[i + 1])) {
      flushPara(); closeLists();
      const head = splitRow(line);
      const seps = splitRow(lines[i + 1]);
      const align = seps.map(function (c) { return c.startsWith(":") && c.endsWith(":") ? "center" : c.endsWith(":") ? "right" : "left"; });
      let html = '<div class="tbl"><table><thead><tr>';
      head.forEach(function (c, k) { html += '<th class="' + align[k] + '">' + inline(c) + "</th>"; });
      html += "</tr></thead><tbody>";
      i += 2;
      while (i < lines.length && lines[i].trim() && lines[i].includes("|") && splitRow(lines[i]).length === head.length) {
        const cells = splitRow(lines[i]);
        html += "<tr>";
        cells.forEach(function (c, k) { html += '<td class="' + align[k] + '">' + inline(c) + "</td>"; });
        html += "</tr>";
        i++;
      }
      html += "</tbody></table></div>";
      out.push(html);
      continue;
    }
    const ul = line.match(/^(\s*)[-*+]\s+(.*)$/);
    const ol = line.match(/^(\s*)\d+[.)]\s+(.*)$/);
    if (ul || ol) {
      flushPara();
      const indent = Math.min(3, Math.floor((ul ? ul[1] : ol[1]).length / 2));
      const kind = ul ? "ul" : "ol";
      while (listStack.length > indent + 1) out.push(listStack.pop() === "ul" ? "</ul>" : "</ol>");
      if (listStack.length === indent + 1 && listStack[listStack.length - 1] !== kind) out.push(listStack.pop() === "ul" ? "</ul>" : "</ol>");
      while (listStack.length < indent + 1) { out.push(kind === "ul" ? "<ul>" : "<ol>"); listStack.push(kind); }
      out.push("<li>" + inline(ul ? ul[2] : ol[2]) + "</li>");
      i++; continue;
    }
    const bq = line.match(/^>\s?(.*)$/);
    if (bq) { flushPara(); closeLists(); out.push("<blockquote>" + inline(bq[1]) + "</blockquote>"); i++; continue; }
    if (/^\s*---+\s*$/.test(line)) { flushPara(); closeLists(); out.push("<hr>"); i++; continue; }
    para.push(line.trim());
    i++;
  }
  flushPara(); closeLists();
  if (fence) out.push("</code></pre>");
  return { html: out.join("\n"), headings: headings };
}
function coverHtml(meta) {
  const kv = [
    ["Document ID", meta.docid || "-"],
    ["Version", meta.version || "1.0"],
    ["Status", meta.status || "Issued for review"],
    ["Date", meta.date || ""],
    ["Owner", meta.owner || ""],
    ["Audience", meta.audience || ""],
    ["Classification", meta.classification || "Internal"],
  ];
  return '<section class="cover"><div class="band"><div class="kicker">' + esc(meta.org || "Coforge FDE Delivery") + " \u00b7 " + esc(meta.programme || "Lumen Bank Dispute Copilot") + '</div></div>' +
    '<div class="title">' + esc(meta.title || "Document") + "</div>" +
    '<p class="subtitle">' + esc(meta.subtitle || "") + "</p>" +
    '<dl class="meta">' + kv.map(function (kv2) { return "<div><dt>" + esc(kv2[0]) + "</dt><dd>" + esc(kv2[1]) + "</dd></div>"; }).join("") + "</dl>" +
    '<div class="stamp">' + esc(meta.stamp || "Fictional training material. All institutions, people, policies, records, and currency in this document are fictional. This document is not legal, regulatory, or certification advice.") + "</div>" +
    '<div class="footer">' + esc(meta.footer || "") + "</div></section>";
}
function tocHtml(headings, pageMap) {
  const items = headings.filter(function (h) { return h.depth <= 2; });
  if (!items.length) return "";
  let got = 0;
  for (const h of items) if (pageMap && pageMap[h.id]) got++;
  const plain = items.length > 3 && got < items.length * 0.8;
  let html = '<section class="toc' + (plain ? " toc-plain" : "") + '"><h2>Contents</h2><ol>';
  for (const h of items) {
    const num = pageMap && pageMap[h.id] ? String(pageMap[h.id]) : "";
    html += '<li class="lvl' + h.depth + '"><span class="t">' + inline(h.text) + '</span><span class="leader"></span><span class="n">' + num + "</span></li>";
  }
  return html + "</ol></section>";
}
function buildHtml(meta, bodyHtml, headings, pageMap) {
  return '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>' + esc(meta.title) + "</title><style>" + CSS + "</style></head><body>" +
    coverHtml(meta) + tocHtml(headings, pageMap) + bodyHtml + "</body></html>";
}
async function waitForChrome(port, timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < (timeoutMs || 20000)) {
    try {
      const r = await fetch("http://127.0.0.1:" + port + "/json/version");
      if (r.ok) return await r.json();
    } catch (e) {}
    await new Promise(function (r) { setTimeout(r, 250); });
  }
  throw new Error("Chrome debug port did not open");
}
function chromeBin() {
  const found = CHROME_CANDIDATES.find(function (p) { return existsSync(p); });
  if (!found) throw new Error("No Chrome or Edge binary found");
  return found;
}
async function printPdf(htmlPath, pdfPath, meta) {
  const port = 9300 + Math.floor(Math.random() * 500);
  const profile = mkdtempSync(join(tmpdir(), "pdfprof-"));
  const chrome = spawn(chromeBin(), [
    "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
    "--remote-debugging-port=" + port, "--user-data-dir=" + profile, "--allow-file-access-from-files", "about:blank",
  ], { stdio: "ignore" });
  let ws = null;
  try {
    const ver = await waitForChrome(port);
    ws = new WebSocket(ver.webSocketDebuggerUrl);
    await new Promise(function (res, rej) { ws.onopen = res; ws.onerror = rej; });
    let id = 0;
    const pending = new Map();
    ws.onmessage = function (ev) {
      const msg = JSON.parse(ev.data);
      if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    };
    function send(method, params, sessionId) {
      return new Promise(function (res) {
        const msgId = ++id;
        pending.set(msgId, res);
        const payload = { id: msgId, method: method, params: params || {} };
        if (sessionId) payload.sessionId = sessionId;
        ws.send(JSON.stringify(payload));
      });
    }
    const created = await send("Target.createTarget", { url: "about:blank" });
    const targetId = created.result.targetId;
    const attached = await send("Target.attachToTarget", { targetId: targetId, flatten: true });
    const sid = attached.result.sessionId;
    await send("Page.enable", {}, sid);
    const url = "file:///" + resolve(htmlPath).replace(/\\/g, "/").replace(/ /g, "%20");
    const loaded = new Promise(function (res) {
      const prev = ws.onmessage;
      ws.onmessage = function (ev) {
        prev(ev);
        const msg = JSON.parse(ev.data);
        if (msg.method === "Page.loadEventFired" && msg.sessionId === sid) res();
      };
    });
    await send("Page.navigate", { url: url }, sid);
    await loaded;
    await new Promise(function (r) { setTimeout(r, 500); });
    const header = '<div style="width:100%;font-size:7pt;color:#5b6b7a;padding:0 12mm 2mm;font-family:Segoe UI,Arial,sans-serif;display:flex;justify-content:space-between;border-bottom:0.4pt solid #d7dee5;">' +
      "<span>" + esc(meta.title || "") + "</span><span>" + esc(meta.docid || "") + " \u00b7 v" + esc(meta.version || "1.0") + "</span></div>";
    const footer = '<div style="width:100%;font-size:7pt;color:#5b6b7a;padding:0 12mm;font-family:Segoe UI,Arial,sans-serif;display:flex;justify-content:space-between;">' +
      "<span>" + esc(meta.classification || "Internal") + " \u00b7 Fictional training data</span><span>Page <span class=\"pageNumber\"></span> of <span class=\"totalPages\"></span></span></div>";
    const printed = await send("Page.printToPDF", {
      printBackground: true, paperWidth: 8.27, paperHeight: 11.69,
      marginTop: 0.75, marginBottom: 0.72, marginLeft: 0.71, marginRight: 0.71,
      displayHeaderFooter: true, headerTemplate: header, footerTemplate: footer, scale: 1,
    }, sid);
    if (printed.error) throw new Error("printToPDF: " + JSON.stringify(printed.error));
    writeFileSync(pdfPath, Buffer.from(printed.result.data, "base64"));
  } finally {
    try { if (ws) ws.close(); } catch (e) {}
    chrome.kill();
    try { rmSync(profile, { recursive: true, force: true }); } catch (e) {}
  }
}
function pageMapFromPdf(pdfPath, headings) {
  let text = "";
  try {
    const { execFileSync } = require("node:child_process");
    text = execFileSync("pdftotext", ["-layout", pdfPath, "-"], { encoding: "utf8", maxBuffer: 32 * 1024 * 1024 });
  } catch (e) { return null; }
  const pages = text.split("\f");
  const map = {};
  pages.forEach(function (pageText, idx) {
    const re = /\[\[H(\d+)\]\]/g;
    let m;
    while ((m = re.exec(pageText)) !== null) {
      const h = headings[Number(m[1])];
      if (h) map[h.id] = idx + 1;
    }
  });
  return map;
}
const args = process.argv.slice(2);
const mdPath = resolve(args[0]);
const outIdx = args.indexOf("--out");
const outDir = outIdx >= 0 ? resolve(args[outIdx + 1]) : join(dirname(mdPath), "out");
mkdirSync(outDir, { recursive: true });
const raw = readFileSync(mdPath, "utf8");
const parts = parseFront(raw);
const meta = parts[0];
const body = parts[1];
const parsed = mdToHtml(body, dirname(mdPath));
const stem = basename(mdPath).replace(/\.md$/, "");
const htmlPath = join(outDir, stem + ".html");
const pdfPath = join(outDir, stem + ".pdf");
writeFileSync(htmlPath, buildHtml(meta, parsed.html, parsed.headings, null));
await printPdf(htmlPath, pdfPath, meta);
let pageMap = pageMapFromPdf(pdfPath, parsed.headings);
let numbers = 0;
if (pageMap) for (const k in pageMap) numbers++;
if (numbers >= parsed.headings.length * 0.5) {
  writeFileSync(htmlPath, buildHtml(meta, parsed.html, parsed.headings, pageMap));
  await printPdf(htmlPath, pdfPath, meta);
}
let pageCount = 0;
try {
  const { execFileSync } = require("node:child_process");
  const info = execFileSync("pdfinfo", [pdfPath], { encoding: "utf8" });
  const m = info.match(/Pages:\s+(\d+)/);
  if (m) pageCount = Number(m[1]);
} catch (e) {}
console.log(JSON.stringify({ md: mdPath, html: htmlPath, pdf: pdfPath, pages: pageCount, headings: parsed.headings.length, tocNumbers: numbers, title: meta.title }));
