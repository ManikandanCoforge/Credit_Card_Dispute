
import fitz, os
pdf = "docs/deck/out/lumen-dispute-copilot-2026-10-29.pdf"
doc = fitz.open(pdf)
print("pages", doc.page_count)
os.makedirs("docs/deck/review/render", exist_ok=True)
for i, page in enumerate(doc):
    print(i+1, page.rect)
    pix = page.get_pixmap(dpi=150)
    pix.save(f"docs/deck/review/render/p{i+1:02d}.png")
print("done")
