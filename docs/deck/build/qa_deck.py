"""Programmatic QA for a deck: text overflow estimate, out-of-slide shapes, text-on-text overlap.

Usage: python qa_deck.py deck.pptx   (needs python-pptx)
Notes: same-row label/value pairs sharing one text box flag as text_overlap (false positive).
Overlap area under ~0.2 in2 is usually noise; treat as advisory, then verify visually.
"""
import math, sys, json
from pptx import Presentation
from pptx.util import Emu

PATH = sys.argv[1]
prs = Presentation(PATH)
W = prs.slide_width / 914400
H = prs.slide_height / 914400
CHAR_W = 0.56  # avg char width as fraction of font size (Segoe UI, conservative)

def walk(shapes):
    for sh in shapes:
        if sh.shape_type == 6:
            yield from walk(sh.shapes)
        else:
            yield sh

def est_height(shape):
    """Estimate rendered text height in inches vs box height."""
    tf = shape.text_frame
    box_w = shape.width / 914400 - 0.04
    total_pt = 0.0
    for para in tf.paragraphs:
        text = "".join(r.text for r in para.runs)
        sizes = [r.font.size.pt for r in para.runs if r.font.size]
        fs = max(sizes) if sizes else 13.0
        cpl = max(8, box_w * 72 / (CHAR_W * fs))
        lines = max(1, math.ceil(len(text) / cpl)) if text else 1
        total_pt += lines * fs * 1.28 + 4
    return total_pt / 72.0

issues = []
for si, slide in enumerate(prs.slides, 1):
    texts = []
    for sh in walk(slide.shapes):
        x, y = sh.left / 914400, sh.top / 914400
        w, h = sh.width / 914400, sh.height / 914400
        if x < -0.02 or y < -0.02 or x + w > W + 0.03 or y + h > H + 0.03:
            issues.append({"slide": si, "kind": "out_of_bounds", "name": sh.shape_id, "where": f"{x:.2f},{y:.2f} {w:.2f}x{h:.2f}"})
        if getattr(sh, "has_text_frame", False) and sh.text_frame.text.strip():
            need = est_height(sh)
            if need > h * 1.1 + 0.06:
                issues.append({"slide": si, "kind": "overflow_est", "text": sh.text_frame.text[:60].replace("\n", " | "), "need": round(need, 2), "box": round(h, 2)})
            texts.append((x, y, w, h, sh.text_frame.text[:24]))
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            ax, ay, aw, ah, at = texts[i]
            bx, by, bw, bh, bt = texts[j]
            ox = min(ax + aw, bx + bw) - max(ax, bx)
            oy = min(ay + ah, by + bh) - max(ay, by)
            if ox > 0.05 and oy > 0.05 and ox * oy > 0.06:
                issues.append({"slide": si, "kind": "text_overlap", "a": at, "b": bt, "area": round(ox * oy, 2)})

print(json.dumps({"slides": len(prs.slides.__iter__.__self__._sldIdLst), "issues": issues}, indent=1))
