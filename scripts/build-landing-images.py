#!/usr/bin/env python3
"""Build the landing page's images from site/img-src/ into site/img/.

  hero.jpg            -> hero-720.webp, hero-1280.webp (4:3), og.jpg (link previews)
  <theme>.jpg         -> <theme>-600.webp (4:5 crop) for the examples grid
  demos/inform.jpg    -> phone-inform.webp (the phone in the hero)

Also writes the photographer credits from site/img-src/CREDITS.json into the
landing page footer. Re-run after swapping a photo; then deploy with
worker/deploy-mayfly.py --pages-only.
"""

import html
import json
import os
import re
import sys

from PIL import Image, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mayfly_ops import ROOT, THEMES  # noqa: E402

SRC = os.path.join(ROOT, "site", "img-src")
OUT = os.path.join(ROOT, "site", "img")
# Where to anchor the crop for each photo, as (x, y) fractions; default is centered.
FOCUS = {"hero": (0.4, 0.5), "rally": (0.35, 0.5), "announce": (0.4, 0.5)}


def save(im, name, quality=74):
    path = os.path.join(OUT, name)
    im.save(path, "WEBP", quality=quality, method=6)
    print("%-22s %4d KB  %dx%d" % (name, os.path.getsize(path) // 1024, im.width, im.height))


def fit(im, w, h, key):
    return ImageOps.fit(im, (w, h), Image.LANCZOS, centering=FOCUS.get(key, (0.5, 0.5)))


def main():
    os.makedirs(OUT, exist_ok=True)

    def load(name):
        return ImageOps.exif_transpose(Image.open(os.path.join(SRC, name))).convert("RGB")

    hero = load("hero.jpg")
    for w in (720, 1280):
        save(fit(hero, w, w * 3 // 4, "hero"), "hero-%d.webp" % w)
    # Link previews: JPEG at the 1.91:1 size every chat app and social site expects.
    og = fit(hero, 1200, 630, "hero")
    og.save(os.path.join(OUT, "og.jpg"), "JPEG", quality=80, optimize=True, progressive=True)
    print("%-22s %4d KB" % ("og.jpg", os.path.getsize(os.path.join(OUT, "og.jpg")) // 1024))
    for t in THEMES:
        if os.path.exists(os.path.join(SRC, t + ".jpg")):
            save(fit(load(t + ".jpg"), 600, 750, t), "%s-600.webp" % t)
        else:
            print("missing site/img-src/%s.jpg" % t)

    shot = os.path.join(ROOT, "demos", "inform.jpg")
    if os.path.exists(shot):
        im = Image.open(shot).convert("RGB")
        im = im.crop((0, 0, im.width, int(im.width * 18.5 / 9)))
        save(im.resize((390, int(390 * 18.5 / 9)), Image.LANCZOS), "phone-inform.webp", quality=80)
    else:
        print("run scripts/render-demos.py first for the phone screenshot")

    credits_path = os.path.join(SRC, "CREDITS.json")
    if os.path.exists(credits_path):
        credits = json.load(open(credits_path))
        seen, links = set(), []
        for c in credits:
            if not c["file"].endswith("-alt.jpg") and c["photographer"] not in seen:
                seen.add(c["photographer"])
                links.append('<a href="%s">%s</a>' % (html.escape(c["photo_page_url"]), html.escape(c["photographer"])))
        page = os.path.join(ROOT, "site", "index.html")
        src = open(page, encoding="utf-8").read()
        new = re.sub(
            r'<p id="credits">.*?</p>',
            '<p id="credits">Photos from Unsplash by %s.</p>' % ", ".join(links),
            src,
            flags=re.S,
        )
        open(page, "w", encoding="utf-8").write(new)
        print("credits: %d photographers" % len(links))


if __name__ == "__main__":
    main()
