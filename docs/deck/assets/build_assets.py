"""Build the three hero assets for the Lumen Bank deck.

Outputs, all in this directory:
  pipeline.svg  3200 x 1100
  boundary.svg  3200 x 1400
  motif.svg     1600 x 1600
  *.png         rendered at 2x with headless Chrome

The text is copied from docs/flow/README.md, the module docstrings, and the
review / record handler in tools/runtime.py. No placeholder strings.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

PAPER = "#FBFAF7"
INK = "#12262E"
INK2 = "#2B454F"
MUTED = "#68777D"
LINE = "#E2DDD2"
LINE2 = "#D3CDC0"
SAND = "#F3EFE6"
TEAL = "#0D6F6A"
TEAL_SOFT = "#E6F2EF"
GREEN = "#1C7A58"
RED = "#B4452F"
RED_SOFT = "#F8ECE8"
AMBER = "#A96900"
NAVY = "#0A1C24"

SERIF = "Georgia, Cambria, 'Times New Roman', serif"
SANS = "'Segoe UI', 'Segoe UI Variable', Arial, sans-serif"
MONO = "'Cascadia Mono', 'Cascadia Code', Consolas, monospace"


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def text(
    x: float,
    y: float,
    s: str,
    size: float = 24,
    fill: str = INK,
    anchor: str = "start",
    family: str = SANS,
    weight: int = 400,
    ls: float = 0,
    opacity: float = 1.0,
    style: str = "",
):
    extra = f' letter-spacing="{ls}"' if ls else ""
    extra += f' font-style="{style}"' if style else ""
    op = f' opacity="{opacity}"' if opacity != 1.0 else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
        f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}"{extra}{op}>'
        f"{esc(s)}</text>"
    )


def rect(x, y, w, h, fill="none", stroke="none", sw=1.0, rx=0, dash=None, op=1.0):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    o = f' opacity="{op}"' if op != 1.0 else ""
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}{o}/>'
    )


def line(x1, y1, x2, y2, stroke=LINE, sw=1.0, dash=None, marker=None, op=1.0):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    m = f' marker-end="url(#{marker})"' if marker else ""
    o = f' opacity="{op}"' if op != 1.0 else ""
    return (
        f'<path d="M{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f}" fill="none" '
        f'stroke="{stroke}" stroke-width="{sw}"{d}{m}{o}/>'
    )


def path(d, stroke=TEAL, sw=3.0, fill="none", op=1.0, cap="square", join="miter", dash=None):
    o = f' opacity="{op}"' if op != 1.0 else ""
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
        f'stroke-linecap="{cap}" stroke-linejoin="{join}"{da}{o}/>'
    )


def svg_open(w, h, title, desc):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-labelledby="t d">',
        f"<title id=\"t\">{esc(title)}</title>",
        f"<desc id=\"d\">{esc(desc)}</desc>",
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0 0 L10 5 L0 10 Z" fill="{TEAL}"/></marker></defs>',
    ]


def header(w, label, asset_no, right_a, right_b):
    out = []
    out.append(text(130, 66, "LUMEN BANK · DISPUTE COPILOT", 20, MUTED, family=MONO, weight=700, ls=2.6))
    out.append(text(130, 96, label, 17, MUTED, family=MONO, ls=2.2))
    out.append(text(w - 130, 66, right_a, 20, MUTED, anchor="end", family=MONO, weight=700, ls=2.2))
    out.append(text(w - 130, 96, right_b, 17, MUTED, anchor="end", family=MONO, ls=2.2))
    out.append(line(130, 132, w - 130, 132, LINE2, 1.4))
    out.append(text(130, 196, asset_no, 20, TEAL, family=MONO, weight=700, ls=3.2))
    return out


def pipeline() -> str:
    W, H = 3200, 1100
    out = svg_open(
        W,
        H,
        "Pipeline: four stages from a bank case list to one approved record",
        "Intake reads GET /v1/cases and validates the body with pydantic. Read turns bytes into typed bodies, retries a 503 and raises BankReadError only after the ladder is exhausted. Assemble builds one contract with six to nine exact-slice citations and raises ContractError when a source cannot support a claim. The human gate binds a sha256 draft hash to an approval and refuses a changed draft with 403 and a duplicate record with 409. All twelve dev cases build a contract.",
    )
    out.append(rect(0, 0, W, H, PAPER))
    out += header(
        W,
        "DECK ASSET · PIPELINE",
        "THE RUN, IN FOUR STAGES",
        "MAIN 8553BB3 · 28 OCT 2026",
        "12 / 12 DEV CASES",
    )
    out.append(text(130, 258, "A case list becomes one record.", 54, INK, family=SERIF))
    out.append(
        text(
            130,
            308,
            "A failed read is retried. A missing quote still stops the build.",
            29,
            INK2,
        )
    )

    cards = [
        {
            "x": 130,
            "zone": "01 · INTAKE",
            "title": "Read the bank",
            "body": [
                "GET /v1/cases: 12 cases.",
                "The body is validated, never guessed.",
                "pydantic validates the body.",
            ],
            "code": ["GET /v1/cases", "CaseListResponse.cases[]"],
            "micro": "BANK CALL",
        },
        {
            "x": 880,
            "zone": "02 · READ",
            "title": "Bytes to typed bodies",
            "body": [
                "200 returns bytes; all else stops.",
                "read_body raises BankReadError.",
                "A 503 is retried, never read as empty.",
            ],
            "code": ["read_body(base_url, path)", "BankReadError"],
            "micro": "TYPED READ AND RETRIED",
        },
        {
            "x": 1630,
            "zone": "03 · ASSEMBLE",
            "title": "Text to a contract",
            "body": [
                "Code assigns class and route.",
                "Each citation is an exact slice.",
                "A missing quote raises ContractError.",
            ],
            "code": ["assemble_contract(record, ...)", "Contract · 10 keys"],
            "micro": "PURE FUNCTION",
        },
        {
            "x": 2380,
            "zone": "04 · HUMAN GATE",
            "title": "Hash, human, record",
            "body": [
                "sha256 binds the draft to review.",
                "A changed draft is refused: 403.",
                "Second record: 409 duplicate_case.",
            ],
            "code": ["POST /v1/reviews 201", "403 approval_missing_or_draft_changed"],
            "micro": "SERVER GATE",
        },
    ]

    # stage labels and the route hairline
    for card in cards:
        out.append(text(card["x"] + 32, 372, card["zone"], 21, TEAL, family=MONO, weight=700, ls=3.0))
    out.append(line(130, 396, 3070, 396, TEAL, 1.5))
    for card in cards:
        out.append(line(card["x"] + 32, 390, card["x"] + 32, 404, TEAL, 2.5))

    for card in cards:
        x = card["x"]
        out.append(line(x, 432, x, 810, TEAL, 3.2))
        out.append(text(x + 32, 474, card["micro"], 17, MUTED, family=MONO, ls=2.4))
        out.append(text(x + 32, 528, card["title"], 44, INK, family=SERIF))
        for i, body_line in enumerate(card["body"]):
            out.append(text(x + 32, 580 + i * 40, body_line, 30, INK2))
        out.append(line(x + 32, 712, x + 668, 712, LINE, 1.0))
        for i, code_line in enumerate(card["code"]):
            out.append(text(x + 32, 750 + i * 31, code_line, 22, MUTED, family=MONO))

    # outcomes that are not stops
    out.append(line(130, 850, 3070, 850, LINE, 1.0))
    out.append(text(130, 892, "OUTCOMES, NOT STOPS", 20, MUTED, family=MONO, weight=700, ls=2.4))
    out.append(text(130, 936, "RETRIED · D07, D10", 26, TEAL, family=MONO, weight=700))
    out.append(text(1150, 936, "MANUAL REVIEW · D05, D06, D07", 26, AMBER, family=MONO, weight=700))
    out.append(text(2350, 936, "DUPLICATE PREVENTED · D09", 26, GREEN, family=MONO, weight=700))

    # footnote
    out.append(line(130, 970, 3070, 970, LINE2, 1.2))
    out.append(
        text(
            130,
            1009,
            "12 OF 12 DEV CASES BUILD A CONTRACT · 0 STOPS",
            23,
            INK,
            family=MONO,
            weight=700,
            ls=1.2,
        )
    )
    out.append(
        text(
            3070,
            1009,
            "12 CASES · 27 TOOL ATTEMPTS · 3 RETRIES · 0 MODEL CALLS",
            23,
            INK,
            anchor="end",
            family=MONO,
            weight=700,
            ls=1.2,
        )
    )
    out.append(
        text(
            130,
            1042,
            "D01 DRAFT SHA256 AF65F68659D94274382D90D07417C94031D0C574722BD7B8850E7700CE13EBD4",
            19,
            MUTED,
            family=MONO,
            ls=1.0,
        )
    )
    out.append(text(1300, 1042, "OPERATOR GATE: PYTHON -M SRC.REVIEW_RUNNER", 19, MUTED, family=MONO, ls=1.0))
    out.append(text(3070, 1042, "FICTIONAL TRAINING DATA", 19, MUTED, anchor="end", family=MONO, ls=1.0))
    out.append("</svg>")
    return "\n".join(out)


def boundary() -> str:
    W, H = 3200, 1400
    out = svg_open(
        W,
        H,
        "Trust boundary: untrusted evidence, controls in code, and the proof behind them",
        "Customer statement, attachment text and merchant note sit on the untrusted side. Controls treat text as data, classify in code, cite exact slices and bind an approval to the draft hash. Proof includes tests, audit rows and the 403 and 409 responses. Review and record are operator steps; the scored run stops at the draft.",
    )
    out.append(rect(0, 0, W, H, PAPER))
    out += header(
        W,
        "DECK ASSET · TRUST BOUNDARY",
        "WHAT IS TRUSTED, WHAT IS ONLY DATA",
        "MAIN 8553BB3 · 28 OCT 2026",
        "FICTIONAL TRAINING DATA",
    )
    out.append(text(130, 258, "Untrusted text in. A code gate out.", 52, INK, family=SERIF))
    out.append(
        text(
            130,
            308,
            "Nothing a customer or merchant writes can choose a class, a citation, or an approval.",
            28,
            INK2,
        )
    )

    # columns and bands
    out.append(rect(130, 352, 800, 48, SAND))
    out.append(rect(990, 352, 1120, 48, TEAL_SOFT))
    out.append(rect(2170, 352, 900, 48, SAND))
    out.append(text(150, 384, "01 · UNTRUSTED INPUT", 20, AMBER, family=MONO, weight=700, ls=3.0))
    out.append(text(1010, 384, "02 · CONTROLS IN CODE", 20, TEAL, family=MONO, weight=700, ls=3.0))
    out.append(text(2190, 384, "03 · PROOF", 20, INK2, family=MONO, weight=700, ls=3.0))
    out.append(text(960, 336, "TRUST BOUNDARY", 16, AMBER, anchor="middle", family=MONO, weight=700, ls=2.4))
    out.append(line(960, 420, 960, 1300, LINE2, 1.2, dash="3 7"))
    out.append(line(2140, 420, 2140, 1300, LINE2, 1.2, dash="3 7"))

    # left: untrusted
    left_items = [
        (470, "Customer statement", "Free text. It may name a rule.", "intake · follow-up"),
        (600, "Attachment text", "Partial, wrong, or absent.", "attachment status"),
        (730, "Merchant note", "Written by the other side.", "note, kept as supplied"),
    ]
    for y, title, body, mono in left_items:
        out.append(text(150, y, title, 33, INK, family=SERIF))
        out.append(text(150, y + 36, body, 26, INK2))
        out.append(text(150, y + 66, mono, 20, MUTED, family=MONO))
    out.append(line(130, 840, 930, 840, LINE, 1.0))
    out.append(text(150, 882, "THE RULE", 20, AMBER, family=MONO, weight=700, ls=3.0))
    out.append(text(150, 928, "Read as data.", 36, INK, family=SERIF))
    out.append(text(150, 968, "Never as an instruction.", 36, INK, family=SERIF))
    out.append(text(150, 1010, "A quote may leave the record. An order may not.", 25, INK2))
    out.append(text(150, 1042, "quote must be an exact slice", 20, MUTED, family=MONO))

    # middle: controls
    rows = [
        (
            470,
            "01 · TREAT AS DATA",
            "Text is evidence, not authority.",
            ["The merchant note is stored, never obeyed.", "Its source id and private token are not copied."],
            "build_merchant keeps 3 keys",
        ),
        (
            660,
            "02 · CLASSIFY IN CODE",
            "Code picks the class and the route.",
            ["Procedure anchors and routing precedence decide.", "A day count or quote that cannot be checked stops."],
            "assemble_contract(record, ...)",
        ),
        (
            850,
            "03 · CITE THE SLICE",
            "Every citation is an exact slice.",
            ["Each case cites six to nine exact slices.", "A quote absent from its source is refused.", "No paraphrase, no citation for a failed read."],
            "quote in source_text",
        ),
        (
            1040,
            "04 · BIND THE APPROVAL",
            "The approval binds the draft hash.",
            ["sha256 of canonical JSON, stored with the review.", "The record write checks it again. A changed draft is 403."],
            "review.hash == digest(draft)",
        ),
    ]
    for y, label, title, body, mono in rows:
        out.append(text(1010, y, label, 20, TEAL, family=MONO, weight=700, ls=2.8))
        out.append(text(1010, y + 38, title, 33, INK, family=SERIF))
        out.append(text(1010, y + 75, body[0], 26, INK2))
        out.append(text(1010, y + 105, body[1], 26, INK2))
        out.append(text(1010, y + 141, mono, 21, MUTED, family=MONO))
        out.append(line(990, y + 165, 2110, y + 165, LINE, 1.0))

    # right: proof
    out.append(text(2190, 470, "TESTS AT 8553BB3", 20, MUTED, family=MONO, weight=700, ls=2.8))
    out.append(text(2190, 520, "1014 tests pass.", 46, INK, family=SERIF))
    out.append(text(2190, 556, "100 percent line coverage over 3404 statements.", 25, INK2))
    out.append(line(2170, 584, 3070, 584, LINE, 1.0))

    out.append(text(2190, 626, "THE GATE ANSWERS", 20, MUTED, family=MONO, weight=700, ls=2.8))
    gate = [
        ("201", "review requested, pending"),
        ("200", "replay with the same key"),
        ("403", "approval missing or draft changed"),
        ("409", "duplicate_case"),
    ]
    for i, (code, label) in enumerate(gate):
        y = 666 + i * 43
        out.append(text(2190, y, code, 26, TEAL, family=MONO, weight=700))
        out.append(text(2262, y, label, 25, INK2))
    out.append(line(2170, 828, 3070, 828, LINE, 1.0))

    out.append(text(2190, 870, "HAND-WALKED D01", 20, MUTED, family=MONO, weight=700, ls=2.8))
    out.append(text(2190, 910, "af65f686...ebd4", 24, INK, family=MONO))
    out.append(text(2190, 942, "dispute-d01", 24, INK, family=MONO))
    out.append(text(2190, 980, "5 audit rows move with it.", 24, INK2))
    out.append(line(2170, 1008, 3070, 1008, LINE, 1.0))

    out.append(text(2190, 1050, "BOUNDARY IN ONE LINE", 20, MUTED, family=MONO, weight=700, ls=2.8))
    out.append(text(2190, 1096, "Text may be quoted. Code decides.", 28, INK, family=SERIF))
    out.append(text(2190, 1130, "A human approves.", 28, INK, family=SERIF))

    # open edge band
    out.append(rect(130, 1230, 2940, 76, SAND))
    out.append(rect(130, 1230, 4, 76, AMBER))
    out.append(text(158, 1260, "OPEN EDGE", 19, AMBER, family=MONO, weight=700, ls=3.0))
    out.append(
        text(
            290,
            1262,
            "Review and record are operator steps. The scored run stops at the draft.",
            24,
            INK2,
        )
    )
    out.append(
        text(
            290,
            1292,
            "#52 escalation merged. Retry merged and wired. ADR-003 model route merged, off by default.",
            21,
            MUTED,
        )
    )
    out.append(line(130, 1330, 3070, 1330, LINE2, 1.2))
    out.append(
        text(
            130,
            1366,
            "NO MODEL CALL ON THE READ PATH · CLASSIFICATION, ROUTING, FACTS, CITATIONS AND DEADLINE COME FROM CODE.",
            20,
            INK,
            family=MONO,
            weight=700,
            ls=1.0,
        )
    )
    out.append(text(3070, 1366, "28 OCT 2026", 20, MUTED, anchor="end", family=MONO, ls=1.0))
    out.append("</svg>")
    return "\n".join(out)


def motif() -> str:
    W = H = 1600
    out = svg_open(
        W,
        H,
        "Cover motif: one route, one stop",
        "Abstract mark on navy: a single thin route crosses a faint technical field and ends at one amber node.",
    )
    out.append(rect(0, 0, W, H, NAVY))

    # faint field, no boxes
    for x in (260, 520, 780, 1040, 1300):
        out.append(line(x, 240, x, 1360, TEAL, 1.0, op=0.18))
    for y in (400, 660, 920, 1180):
        out.append(line(180, y, 1420, y, TEAL, 1.0, op=0.13))

    # one route, squared turns, ending at the node
    route = "M 180 1280 H 520 V 1080 H 820 V 860 H 1080 V 700 H 1160"
    out.append(path(route, TEAL_SOFT, 3.0, op=0.95))
    # two alternatives that stop short
    out.append(path("M 180 1210 H 470", TEAL_SOFT, 1.4, op=0.28))
    out.append(path("M 180 1350 H 570 V 1150 H 760", TEAL_SOFT, 1.4, op=0.28))
    out.append(path("M 180 1140 H 430 V 980 H 700", TEAL_SOFT, 1.4, op=0.18))

    # stop ticks on the alternatives
    for x, y in ((470, 1210), (760, 1150), (700, 980)):
        out.append(line(x, y - 7, x, y + 7, TEAL_SOFT, 1.6, op=0.4))

    # the single stop
    out.append(line(1160, 650, 1160, 750, TEAL_SOFT, 1.2, op=0.45))
    out.append(line(1110, 700, 1210, 700, TEAL_SOFT, 1.2, op=0.45))
    out.append(f'<circle cx="1160" cy="700" r="36" fill="none" stroke="{AMBER}" stroke-width="1.4" opacity="0.55"/>')
    out.append(f'<circle cx="1160" cy="700" r="15" fill="{AMBER}"/>')

    out.append("</svg>")
    return "\n".join(out)


def render_png(svg_name: str, w: int, h: int) -> None:
    svg_path = HERE / svg_name
    png_path = svg_path.with_suffix(".png")
    scale = 2
    chrome = Path(r"C:/Program Files/Google/Chrome/Application/chrome.exe")
    if not chrome.exists():
        chrome = Path(r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    if not chrome.exists():
        raise SystemExit("no Chrome or Edge binary found")
    profile = Path(os.environ.get("DECK_CHROME_PROFILE", str(HERE / "_chrome")))
    profile.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(chrome),
        "--headless=new",
        "--disable-gpu",
        f"--user-data-dir={profile}",
        "--hide-scrollbars",
        f"--force-device-scale-factor={scale}",
        f"--window-size={w},{h}",
        "--virtual-time-budget=2000",
        f"--screenshot={png_path}",
        svg_path.resolve().as_uri(),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit(f"chrome failed for {svg_name}")
    from PIL import Image

    with Image.open(png_path) as im:
        print(f"{png_path.name}: {im.size[0]}x{im.size[1]} {im.mode}")


def main() -> None:
    assets = {
        "pipeline.svg": (pipeline(), 3200, 1100),
        "boundary.svg": (boundary(), 3200, 1400),
        "motif.svg": (motif(), 1600, 1600),
    }
    for name, (content, w, h) in assets.items():
        (HERE / name).write_text(content + "\n", encoding="utf-8")
        print(f"wrote {name} ({w}x{h})")
    for name, (_, w, h) in assets.items():
        render_png(name, w, h)


if __name__ == "__main__":
    main()
