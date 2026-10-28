"""Crop the deck plates to their diagram band.

Usage: python make_bare.py  (writes docs/deck/assets/pipeline_bare.png and
boundary_bare.png). Deterministic: fixed pixel boxes, no resampling.

The plates ship with their own chrome, headline, lede and footer, which would
duplicate the deck slide around them, and with paper gutters that stop the
diagram from filling the measure. These crops keep only the diagram band and
the two honesty strips, with the left and right content edges close to the
crop edge so the mount can fill 12.09 in.
"""
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")

CROPS = {
    "pipeline": (250, 665, 6150, 2044),
    "boundary": (250, 700, 5435, 2640),
}


def make_motif():
    """Knock the navy tile out of the cover motif.

    motif.png is a square plate of exact deck navy, so on a navy slide it shows
    as a one-value lighter rectangle whose edge cuts the headline. Turning the
    background into alpha leaves only the drawn lines.
    """
    import numpy as np

    src = os.path.join(ASSETS, "motif.png")
    dst = os.path.join(ASSETS, "motif_alpha.png")
    im = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)
    lum = 0.299 * im[:, :, 0] + 0.587 * im[:, :, 1] + 0.114 * im[:, :, 2]
    alpha = np.clip((lum - 24.0) / 126.0, 0.0, 1.0) ** 0.6
    out = np.dstack([im, alpha * 255.0]).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(dst, optimize=True)
    print("motif -> %s  %dx%d" % (os.path.basename(dst), im.shape[1], im.shape[0]))


def main():
    make_motif()
    for name, box in CROPS.items():
        src = os.path.join(ASSETS, name + ".png")
        dst = os.path.join(ASSETS, name + "_bare.png")
        im = Image.open(src)
        out = im.crop(box)
        out.save(dst, optimize=True)
        print("%s -> %s  %dx%d" % (name, os.path.basename(dst), out.size[0], out.size[1]))


if __name__ == "__main__":
    main()
