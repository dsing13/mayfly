#!/usr/bin/env python3
"""Inject the shared widget block (_widgets.html) into the 8 Mayfly themes.

Adds per theme:
  --hi CSS var (theme accent for RSVP buttons)
  share button in .cta-row (all themes)
  event section (countdown + calendar + directions) after </header>
    - celebrate/invite/sell/remember/rally/play: full version
    - inform: directions-only version
    - announce: none
  RSVP section before the contact section
    - celebrate/invite/rally/play only
  shared widget CSS (before </style>) + JS (before </body>)

Idempotent: skips pieces already present. Source of truth for the widgets
is site/themes/_widgets.html — edit that, re-run this.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TDIR = os.path.join(os.path.dirname(HERE), "site", "themes")

CFG = {
    "celebrate": {"hi": "#E8622C", "evsec": "full", "rsvp": True},
    "invite":    {"hi": "#96702A", "evsec": "full", "rsvp": True},
    "announce":  {"hi": "#B25F6E", "evsec": None,   "rsvp": False},
    "sell":      {"hi": "#B45309", "evsec": "full", "rsvp": False},
    "remember":  {"hi": "#7C5E33", "evsec": "full", "rsvp": False},
    "rally":     {"hi": "#96241B", "evsec": "full", "rsvp": True},
    "inform":    {"hi": "#96600F", "evsec": "dir",  "rsvp": False},
    "play":      {"hi": "#B81F63", "evsec": "full", "rsvp": True},
}

EVSEC_FULL = """<section class="evsec" hidden>
  <div class="wrap">
    <div class="ev-count" data-event="{{event_iso}}">
      <div class="cell"><div class="n" data-u="d">&ndash;</div><div class="l">days</div></div>
      <div class="cell"><div class="n" data-u="h">&ndash;</div><div class="l">hours</div></div>
      <div class="cell"><div class="n" data-u="m">&ndash;</div><div class="l">mins</div></div>
      <div class="cell"><div class="n" data-u="s">&ndash;</div><div class="l">secs</div></div>
    </div>
    <p class="ev-note" data-evnote></p>
    <div class="ev-actions">
      <a class="chip" data-cal hidden>&#x1F4C5; Add to calendar</a>
      <a class="chip" data-dir data-venue="{{venue_text}}" hidden>&#x1F4CD; Get directions</a>
    </div>
  </div>
</section>
"""

EVSEC_DIR = """<section class="evsec" hidden>
  <div class="wrap">
    <div class="ev-actions">
      <a class="chip" data-dir data-venue="{{venue_text}}" hidden>&#x1F4CD; Get directions</a>
    </div>
  </div>
</section>
"""

RSVP_SEC = """<section style="padding-top:0" class="rsvpsec" hidden>
  <div class="wrap">
    <p class="kicker">RSVP</p>
    <div class="rsvp-btns">
      <a class="btn-rsvp yes" data-rsvp="{{rsvp_contact}}" data-answer="yes" href="#">Count me in &#x2713;</a>
      <a class="btn-rsvp no" data-rsvp="{{rsvp_contact}}" data-answer="no" href="#">Can&rsquo;t make it</a>
    </div>
  </div>
</section>
"""

SHARE_BTN = '<button type="button" class="btn-ghost" data-share>&#x2197; Share</button>'

DOC_LINES = """    {{event_iso}}        -> .ev-count data-event (ISO datetime; countdown + calendar; hidden when empty)
    {{venue_text}}       -> directions chip query (Google Maps link; hidden when empty)
    {{rsvp_contact}}     -> RSVP buttons (email or phone; mailto:/sms: prefilled; hidden when empty)
"""


def main():
    wpath = os.path.join(TDIR, "_widgets.html")
    w = open(wpath).read()
    m = re.search(r"<style>(.*?)</style>\s*<script>(.*?)</script>", w, re.S)
    if not m:
        print("could not parse _widgets.html"); sys.exit(1)
    css, js = m.group(1), m.group(2)

    for theme, cfg in CFG.items():
        p = os.path.join(TDIR, theme + ".html")
        h = open(p).read()
        changed = []

        # 1. --hi var
        if "--hi:" not in h:
            h = h.replace(":root{", ":root{--hi:%s;" % cfg["hi"], 1)
            changed.append("hi")

        # 2. share button in cta-row
        if "data-share" not in h:
            old = '<div class="cta-row">{{cta_html}}</div>'
            if old in h:
                h = h.replace(old, '<div class="cta-row">{{cta_html}}' + SHARE_BTN + "</div>", 1)
                changed.append("share")

        # 3. event section after </header>
        if cfg["evsec"] and 'class="evsec"' not in h:
            block = EVSEC_FULL if cfg["evsec"] == "full" else EVSEC_DIR
            h = h.replace("</header>", "</header>\n" + block, 1)
            changed.append("evsec")

        # 4. RSVP section before contact section
        if cfg["rsvp"] and 'class="rsvpsec"' not in h:
            pat = re.compile(r'(<section style="padding-top:0">\s*<div class="wrap">\s*<div class="contact">)')
            h2, n = pat.subn(RSVP_SEC + r"\1", h, count=1)
            if n:
                h = h2; changed.append("rsvp")
            else:
                print(theme + ": WARNING could not place RSVP section")

        # 5. widget CSS before </style> (versioned: re-inject when _widgets.html changes)
        css_ver = re.search(r"MAYFLY WIDGETS (v\d+)", w)
        css_ver = css_ver.group(1) if css_ver else "v1"
        if ("WIDGETS " + css_ver) not in h:
            # drop any older injected widget CSS first
            h = re.sub(r"/\* ---------- event section ---------- \*/.*?"
                       r"\.lb-p\{left:10px\}\.lb-n\{right:10px\}\n",
                       "", h, flags=re.S)
            h = h.replace("</style>", css + "\n</style>", 1)
            # stamp the version
            h = h.replace("</style>", "<!--WIDGETS %s-->\n</style>" % css_ver, 1)
            changed.append("css")

        # 6. widget JS before </body> (versioned: re-inject when _widgets.html changes)
        js_ver = re.search(r"WIDGETS-JS (v\\d+)", w)
        js_ver = js_ver.group(1) if js_ver else "v1"
        if ("WIDGETS-JS " + js_ver) not in h:
            h2, n = re.subn(r"<script>.*?touchstart.*?</script>", "", h, flags=re.S)
            if n or "touchstart" not in h:
                h = h2 if n else h
                h = h.replace("</body>", "<script>" + js + "\n</script>\n</body>", 1)
                changed.append("js")

        # 7. document new placeholders in the variable-map comment
        if "{{event_iso}}" not in h.split("-->")[0]:
            h = h.replace("-->", DOC_LINES + "-->", 1)
            changed.append("docs")

        if changed:
            open(p, "w").write(h)
        print("%-10s %s" % (theme, ",".join(changed) if changed else "already current"))


if __name__ == "__main__":
    main()
