
import sys, fitz
pdf = sys.argv[1]
png = sys.argv[2]
doc = fitz.open(pdf)
print("pages:", doc.page_count)
for p in doc:
    r = p.rect
    print("page", p.number+1, "size pt: %.2f x %.2f" % (r.width, r.height), "mm: %.1f x %.1f" % (r.width/72*25.4, r.height/72*25.4))
page = doc[0]
# ink bbox via pixel scan of a grayscale render at 300 dpi
pix = page.get_pixmap(dpi=300, colorspace=fitz.csGRAY)
import numpy as np
arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
mask = arr < 245
ys, xs = np.where(mask)
dpi = 300
px_mm = dpi / 25.4
left_mm  = xs.min() / px_mm
right_mm = (pix.width - 1 - xs.max()) / px_mm
top_mm   = ys.min() / px_mm
bot_mm   = (pix.height - 1 - ys.max()) / px_mm
print("ink margins mm: left %.1f right %.1f top %.1f bottom %.1f" % (left_mm, right_mm, top_mm, bot_mm))
print("min clear: %.1f mm" % min(left_mm, right_mm, top_mm, bot_mm))
# text inventory: smallest font size
sizes = {}
for b in page.get_text("dict")["blocks"]:
    for l in b.get("lines", []):
        for s in l["spans"]:
            t = s["text"].strip()
            if t:
                k = round(s["size"], 1)
                sizes.setdefault(k, []).append(t)
print("font sizes used:")
for k in sorted(sizes):
    print("  %5.1f pt  n=%d  e.g. %r" % (k, len(sizes[k]), sizes[k][0][:60]))
pix2 = page.get_pixmap(dpi=150)
pix2.save(png)
print("png:", png, pix2.width, "x", pix2.height)
