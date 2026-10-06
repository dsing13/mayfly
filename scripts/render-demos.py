#!/usr/bin/env python3
"""Render the 8 example sites locally, and screenshot them if Chrome is around.

Builds each theme from examples/vars-<theme>.json and examples/photos/<theme>/
with build-site.py --out, writing demos/<theme>.html (+ demos/img/). Then, if
a Chrome/Chromium binary is found (or CHROME is set), saves a 390px-wide
phone screenshot to demos/<theme>.png.

Usage: render-demos.py [theme ...]     (defaults to all 8)
Preview: python3 -m http.server -d demos 8000, then open localhost:8000/<theme>.html
"""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mayfly_ops import ROOT, THEMES  # noqa: E402

DEMOS = os.path.join(ROOT, "demos")
CHROME_CANDIDATES = [
    os.environ.get("CHROME", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/opt/meta-chromium/chrome",
    shutil.which("chromium") or "",
    shutil.which("google-chrome") or "",
]
TITLES = {
    "celebrate": "Mia turns 7",
    "invite": "June & Marcus",
    "announce": "Nora Elise Hart",
    "sell": "The Morningside yard sale",
    "remember": "Eleanor “Nana” Whitaker",
    "rally": "Freedom Park cleanup day",
    "inform": "Have you seen Biscuit?",
    "play": "The Dilworth scavenger hunt",
}


def chrome():
    return next((c for c in CHROME_CANDIDATES if c and os.path.exists(c)), None)


def shot(browser, theme):
    """Phone-width screenshot. Headless Chrome won't make a window narrower
    than ~500px, so the page renders in a 390px iframe and the image is cropped."""
    frame = os.path.join(DEMOS, "_frame.html")
    with open(frame, "w") as f:
        f.write('<!doctype html><body style="margin:0"><iframe src="%s.html" width="390" height="2600" '
                'style="border:0;display:block"></iframe>' % theme)
    png = os.path.join(DEMOS, theme + ".png")
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=2", "--window-size=600,2600",
                    "--virtual-time-budget=4000", "--screenshot=" + png, "file://" + frame],
                   check=False, capture_output=True)
    os.unlink(frame)
    try:
        from PIL import Image
        im = Image.open(png)
        im.crop((0, 0, 780, im.height)).convert("RGB").save(png[:-4] + ".jpg", quality=78, optimize=True)
        os.unlink(png)
        png = png[:-4] + ".jpg"
    except ImportError:
        pass
    print("screenshot:", os.path.relpath(png, ROOT))


def main():
    themes = sys.argv[1:] or THEMES
    os.makedirs(DEMOS, exist_ok=True)
    browser = chrome()
    for t in themes:
        out = os.path.join(DEMOS, t + ".html")
        subprocess.run(
            [
                sys.executable,
                os.path.join(HERE, "build-site.py"),
                "--theme",
                t,
                "--sub",
                t,
                "--ttl-days",
                "7",
                "--title",
                TITLES[t],
                "--vars",
                os.path.join(ROOT, "examples", "vars-%s.json" % t),
                "--images",
                os.path.join(ROOT, "examples", "photos", t),
                "--out",
                out,
            ],
            check=True,
        )
        if browser:
            shot(browser, t)
    if not browser:
        print("no Chrome found; set CHROME=/path/to/chrome for screenshots")


if __name__ == "__main__":
    main()
