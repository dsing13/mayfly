#!/usr/bin/env python3
"""Build a Mayfly site from a theme template and publish it.

Usage:
  build-site.py --theme celebrate --sub mia-turns-7 --ttl-days 7 --tier week \\
      --title "Mia turns 7" --vars vars.json [--images ./photos/] [--pin] [--out page.html]

vars.json keys fill {{placeholders}} in the theme (see the variable map at the
top of each theme). A placeholder can carry a default, {{details_heading|The
details}}, used when vars.json leaves the key out. Keys ending in _html, plus
title, subtitle and qr_svg, are inserted as HTML; every other value is
escaped, so an address with a quote in it can't break the page.

Photos in --images are rotated upright, stripped of EXIF (including GPS),
resized to 1600px, and published as /_img/<sub>/photo-N-<hash>.jpg. In
vars.json refer to them as /_img/<sub>/photo-N.jpg; the hashed names are
swapped in so browsers can cache them for good.

--pin publishes a permanent example (the expiry sweep skips it).
--out writes the page and its photos locally instead of publishing.
"""

import argparse
import base64
import hashlib
import html as htmlmod
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

from mayfly_ops import APEX, ROOT, THEMES, admin_api, load_env

SUB_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
PLACEHOLDER_RE = re.compile(r"\{\{([a-z0-9_]+)(?:\|([^}]*))?\}\}")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def is_raw(key):
    return key.endswith("_html") or key in ("title", "subtitle", "qr_svg")


def plain_text(s):
    """'Mia turns <em>7!</em>' -> 'Mia turns 7!' (entities decoded)."""
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def expiry_label(ttl_days, pinned):
    if pinned:
        return "Example page · made with Mayfly"
    return "This page comes down in %s" % ("1 day" if ttl_days == 1 else "%d days" % ttl_days)


def qr_svg(url):
    try:
        import segno
    except ImportError:
        print("note: pip install segno to add a QR code to the page")
        return ""
    buf = io.BytesIO()
    segno.make(url, error="m").save(
        buf, kind="svg", xmldecl=False, svgns=True, scale=1, border=0, dark="#151412", omitsize=True
    )
    return buf.getvalue().decode()


def prep_images(imgdir):
    """Return [(plain_name, hashed_name, jpeg_bytes)] in filename order."""
    if not imgdir:
        return []
    if not os.path.isdir(imgdir):
        sys.exit("--images: %s is not a folder" % imgdir)
    try:
        from PIL import Image, ImageOps
    except ImportError:
        sys.exit("Pillow is required for --images (pip install Pillow)")
    out = []
    files = [f for f in sorted(os.listdir(imgdir)) if f.lower().endswith(IMAGE_EXTS)]
    for i, fn in enumerate(files, 1):
        im = ImageOps.exif_transpose(Image.open(os.path.join(imgdir, fn))).convert("RGB")
        im.thumbnail((1600, 1600), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80, optimize=True, progressive=True)  # no EXIF written
        data = buf.getvalue()
        plain = "photo-%d.jpg" % i
        hashed = "photo-%d-%s.jpg" % (i, hashlib.sha256(data).hexdigest()[:8])
        out.append((plain, hashed, data))
        print("image: %-24s -> photo-%d.jpg (%d KB)" % (fn, i, len(data) // 1024))
    return out


def render(theme, varmap):
    with open(os.path.join(ROOT, "site", "themes", theme + ".html"), encoding="utf-8") as f:
        tpl = f.read()
    missing = set()

    def fill(m):
        key, default = m.group(1), m.group(2)
        if key in varmap:
            v = str(varmap[key])
            return v if is_raw(key) else htmlmod.escape(v, quote=True)
        if default is None:
            missing.add(key)
            return ""
        return default

    out = PLACEHOLDER_RE.sub(fill, tpl)
    # Drop the theme's docs comment, empty social-preview tags, and an empty hero photo.
    out = re.sub(r"<!--.*?-->\n?", "", out, flags=re.S)
    out = re.sub(r'<meta (?:property|name)="[^"]+" content="">\n?', "", out)
    out = re.sub(r'\s*<img class="hero-photo" src=""[^>]*>', "", out)
    return out, sorted(missing)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--theme", required=True, choices=THEMES)
    ap.add_argument("--sub", required=True)
    ap.add_argument("--ttl-days", required=True, type=int)
    ap.add_argument("--tier", default="")
    ap.add_argument("--title", required=True, help="page title; plain text")
    ap.add_argument("--vars", default="{}", help="JSON file, or an inline JSON object")
    ap.add_argument("--images", default="")
    ap.add_argument("--pin", action="store_true", help="permanent example; never expires")
    ap.add_argument("--out", default="", help="write locally instead of publishing")
    ap.add_argument("--worker-url", default="", help="override MAYFLY_WORKER_URL")
    args = ap.parse_args()

    sub = args.sub.lower().strip()
    if not SUB_RE.match(sub):
        sys.exit("bad --sub: lowercase letters, digits and dashes only")
    try:
        varmap = (
            json.loads(args.vars) if args.vars.strip().startswith("{") else json.load(open(args.vars, encoding="utf-8"))
        )
    except Exception as e:
        sys.exit("vars parse failed: %s" % e)

    site_url = "https://%s.%s/" % (sub, APEX)
    expires = datetime.now(timezone.utc) + timedelta(days=args.ttl_days)
    page_title = plain_text(args.title)
    hero = varmap.get("hero_image", "")
    computed = {
        "page_title": page_title,
        "og_description": plain_text(varmap.get("subtitle", "")),
        "og_image": (site_url.rstrip("/") + hero) if hero.startswith("/") else hero,
        "site_url": site_url,
        "expires_at_iso": "" if args.pin else expires.isoformat(),
        "expires_label": expiry_label(args.ttl_days, args.pin),
    }
    for k, v in computed.items():
        varmap.setdefault(k, v)
    varmap.setdefault("title", htmlmod.escape(page_title))
    if "qr_svg" not in varmap and not args.out:
        varmap["qr_svg"] = qr_svg(site_url)

    html, missing = render(args.theme, varmap)
    if missing:
        print("note: no value for %s (left blank)" % ", ".join(missing))

    images = prep_images(args.images)

    if args.out:
        outdir = os.path.dirname(os.path.abspath(args.out))
        os.makedirs(os.path.join(outdir, "img"), exist_ok=True)
        for plain, hashed, data in images:
            local = "img/%s-%s" % (sub, hashed)
            with open(os.path.join(outdir, local), "wb") as f:
                f.write(data)
            html = html.replace(site_url.rstrip("/") + "/_img/%s/%s" % (sub, plain), local)
            html = html.replace("/_img/%s/%s" % (sub, plain), local)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(html)
        print("wrote", args.out)
        return

    for plain, hashed, _ in images:
        html = html.replace("/_img/%s/%s" % (sub, plain), "/_img/%s/%s" % (sub, hashed))
    env = load_env()
    if args.worker_url:
        env["MAYFLY_WORKER_URL"] = args.worker_url
    res = admin_api(
        env,
        "POST",
        "/api/sites",
        {
            "sub": sub,
            "html": html,
            "ttlDays": args.ttl_days,
            "tier": args.tier or ("example" if args.pin else "%dd" % args.ttl_days),
            "title": page_title,
            "pinned": args.pin,
            "images": [{"name": hashed, "b64": base64.b64encode(data).decode()} for _, hashed, data in images],
        },
    )
    print(json.dumps(res, indent=2))
    if res.get("ok"):
        print("live:", site_url)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
