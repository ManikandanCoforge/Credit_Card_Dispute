"""Drop duplicate <a:pPr> inside each <a:p> of pptxgenjs slide XML.

pptxgenjs (older versions) writes one <a:pPr> per run; OOXML allows only the first. LibreOffice
tolerates it, PowerPoint re-lays-out the paragraph. minidom-based, no regex.

Usage: python fix_ppr.py deck.pptx
"""
import sys, zipfile, shutil
from xml.dom import minidom

src = sys.argv[1]
tmp = src + ".tmp"

with zipfile.ZipFile(src, "r") as zin:
    names = zin.namelist()
    data = {n: zin.read(n) for n in names}

fixed = 0
for n in names:
    if not (n.startswith("ppt/slides/slide") and n.endswith(".xml")):
        continue
    doc = minidom.parseString(data[n])
    changed = False
    for p in doc.getElementsByTagName("a:p"):
        pprs = [c for c in p.childNodes if c.nodeType == 1 and c.tagName == "a:pPr"]
        for extra in pprs[1:]:
            p.removeChild(extra)
            changed = True
            fixed += 1
    if changed:
        data[n] = doc.toxml().encode("utf-8")

with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for n in names:
        zout.writestr(n, data[n])
shutil.move(tmp, src)
print(f"removed {fixed} duplicate a:pPr elements")
