"""Render every PDF page to out/preview/slide-NN.png at 1600 px wide."""
import sys, os
import fitz

pdf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "out", "lumen-dispute-copilot-2026-10-29.pdf")
out = os.path.join(os.path.dirname(pdf), "preview")
os.makedirs(out, exist_ok=True)
doc = fitz.open(pdf)
zoom = 1600 / doc[0].rect.width
for i, page in enumerate(doc, 1):
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    path = os.path.join(out, "slide-%02d.png" % i)
    pix.save(path)
print("rendered %d pages to %s" % (doc.page_count, out))
