#!/usr/bin/env python3
"""Copy the shared base CSS and widget JS from site/themes/_widgets.html into
all 8 themes.

Each theme carries two markers:
  /* mayfly:shared */ ... /* /mayfly:shared */   inside its <style>
  <script>/* mayfly:widgets */ ... </script>     before </body>
Everything between them is replaced on every run, so the script is
idempotent. Edit _widgets.html, then re-run this. Never hand-edit the
injected copies.

Usage: inject-widgets.py [--check]   (--check exits 1 if any theme is stale)
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mayfly_ops import ROOT, THEMES  # noqa: E402

TDIR = os.path.join(ROOT, "site", "themes")
CSS_RE = re.compile(r"/\* mayfly:shared(?: v\d+)? \*/.*?/\* /mayfly:shared \*/", re.S)
JS_RE = re.compile(r"<script>\s*/\* mayfly:widgets(?: v\d+)? \*/.*?</script>", re.S)


def main():
    check = "--check" in sys.argv
    src = open(os.path.join(TDIR, "_widgets.html"), encoding="utf-8").read()
    css = CSS_RE.search(src)
    js = JS_RE.search(src)
    if not css or not js:
        sys.exit("could not find the shared CSS/JS markers in _widgets.html")
    stale = []
    for theme in THEMES:
        path = os.path.join(TDIR, theme + ".html")
        h = open(path, encoding="utf-8").read()
        if not CSS_RE.search(h) or not JS_RE.search(h):
            sys.exit("%s: missing mayfly:shared or mayfly:widgets marker" % theme)
        new = CSS_RE.sub(lambda m: css.group(0), h, count=1)
        new = JS_RE.sub(lambda m: js.group(0), new, count=1)
        if new != h:
            stale.append(theme)
            if not check:
                open(path, "w", encoding="utf-8").write(new)
        print("%-10s %s" % (theme, ("stale" if check else "updated") if new != h else "current"))
    if check and stale:
        sys.exit(1)


if __name__ == "__main__":
    main()
