#!/usr/bin/env python3
"""Subset Fredoka and inline it into the landing page, form, and the themes that use it.

Reads site/fonts/Fredoka.ttf (variable, SIL OFL), pins it to weight 600,
keeps Latin text and punctuation, and writes the WOFF2 as a base64 data URI
between the /* mayfly:font */ markers. Inlining means no extra request and no
flash of fallback text; both pages' CSP already allows data: fonts.

Usage: build-font.py
"""
import base64
import io
import os
import re
import sys

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mayfly_ops import ROOT  # noqa: E402

TEXT = "".join(chr(c) for c in range(0x20, 0x7F)) + "’‘“”–—·…×"
MARK = re.compile(r"/\* mayfly:font \*/.*?/\* /mayfly:font \*/", re.S)


def main():
    font = TTFont(os.path.join(ROOT, "site", "fonts", "Fredoka.ttf"))
    axes = {"wght": 600}
    if any(a.axisTag == "wdth" for a in font["fvar"].axes):
        axes["wdth"] = 100
    font = instancer.instantiateVariableFont(font, axes)
    opts = subset.Options(layout_features=["kern", "liga"], hinting=False, name_IDs=[1, 2])
    sub = subset.Subsetter(opts)
    sub.populate(text=TEXT)
    sub.subset(font)
    font.flavor = "woff2"
    buf = io.BytesIO()
    font.save(buf)
    data = base64.b64encode(buf.getvalue()).decode()
    css = ('/* mayfly:font */@font-face{font-family:Fredoka;font-weight:600;font-display:block;'
           'src:url(data:font/woff2;base64,%s) format("woff2")}/* /mayfly:font */' % data)
    for page in ("index.html", "start.html", "themes/celebrate.html", "themes/announce.html", "themes/play.html"):
        path = os.path.join(ROOT, "site", page)
        src = open(path, encoding="utf-8").read()
        if not MARK.search(src):
            sys.exit("%s: missing mayfly:font markers" % page)
        open(path, "w", encoding="utf-8").write(MARK.sub(lambda m: css, src, count=1))
    print("font: %d KB inlined" % (len(data) // 1024))


if __name__ == "__main__":
    main()
