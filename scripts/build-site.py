#!/usr/bin/env python3
"""Build a Mayfly site from a theme template and publish it.

Usage:
  build-site.py --theme celebrate --sub mia-turns-7 --ttl-days 7 --tier week
      --title "Mia turns 7!" --vars vars.json [--images ./photos/]

vars.json keys map to {{placeholders}} in the theme: subtitle, hero_image,
details_html, gallery_html, contact_html, qr_svg. expires_at_iso is computed.
Images in --images are resized, uploaded via the API, and referenced as
/_img/<sub>/<name>. Set hero_image to /_img/<sub>/hero.jpg etc.
"""
import argparse
import base64
import html as htmlmod
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENV_PATH = os.path.join(ROOT, "hidden_files", "mayfly.env")

THEMES = ["celebrate", "invite", "announce", "sell",
          "remember", "rally", "inform", "play"]


def load_env():
    env = {}
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def api(env, method, path, body=None):
    # curl, not urllib: Python urllib is flaky through this VM's egress proxy
    # vs Cloudflare edge (RemoteDisconnected/timeouts); curl works reliably.
    import subprocess
    cmd = ["curl", "-s", "--max-time", "120", "-X", method,
           "-A", ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
           "-H", "Authorization: Bearer " + env["MAYFLY_ADMIN_TOKEN"]]
    if body is not None:
        import tempfile, os
        fd, tmp = tempfile.mkstemp(suffix='.json')
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(json.dumps(body))
            cmd += ["-H", "Content-Type: application/json",
                    "--data-binary", "@" + tmp]
            cmd.append(env["MAYFLY_WORKER_URL"] + path)
            out = subprocess.run(cmd, capture_output=True, text=True)
        finally:
            os.unlink(tmp)
    else:
        cmd.append(env["MAYFLY_WORKER_URL"] + path)
        out = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(out.stdout)


def prep_images(sub, imgdir):
    images = []
    if not imgdir or not os.path.isdir(imgdir):
        return images
    try:
        from PIL import Image
    except ImportError:
        print("PIL not available — skipping images")
        return images
    for i, fn in enumerate(sorted(os.listdir(imgdir))):
        if not fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        p = os.path.join(imgdir, fn)
        im = Image.open(p).convert("RGB")
        im.thumbnail((1600, 1600))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
        name = "photo-%d.jpg" % (i + 1)
        images.append({"name": name, "ct": "image/jpeg",
                       "b64": base64.b64encode(buf.getvalue()).decode()})
        print("image: %s -> /_img/%s/%s (%d KB)"
              % (fn, sub, name, len(buf.getvalue()) // 1024))
    return images


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", required=True, choices=THEMES)
    ap.add_argument("--sub", required=True)
    ap.add_argument("--ttl-days", required=True, type=int)
    ap.add_argument("--tier", default="")
    ap.add_argument("--title", required=True)
    ap.add_argument("--vars", default="{}")
    ap.add_argument("--images", default="")
    ap.add_argument("--worker-url", default="",
                    help="Override MAYFLY_WORKER_URL from mayfly.env")
    args = ap.parse_args()

    tpl_path = os.path.join(ROOT, "site", "themes", args.theme + ".html")
    with open(tpl_path) as f:
        html = f.read()

    try:
        varmap = json.loads(args.vars) if args.vars.strip().startswith("{") \
            else json.load(open(args.vars))
    except Exception as e:
        print("vars parse failed:", e)
        sys.exit(1)

    expires = datetime.now(timezone.utc) + timedelta(days=args.ttl_days)
    varmap.setdefault("title", args.title)
    varmap["expires_at_iso"] = expires.isoformat()
    for k, v in varmap.items():
        html = html.replace("{{" + k + "}}", str(v))
    # Swap the theme's sample <title> tag for the real title.
    html = re.sub(r"<title>.*?</title>",
                  "<title>" + htmlmod.escape(args.title) + "</title>",
                  html, count=1, flags=re.S)
    if "{{" in html and "}}" in html:
        print("warning: unreplaced placeholders remain")
    # Safety net: never ship a raw {{placeholder}} to a customer page.
    html = re.sub(r"\{\{[a-z0-9_]+\}\}", "", html)

    env = load_env()
    if args.worker_url:
        env["MAYFLY_WORKER_URL"] = args.worker_url.rstrip("/")
    images = prep_images(args.sub, args.images)
    res = api(env, "POST", "/api/sites", {
        "sub": args.sub, "html": html, "ttlDays": args.ttl_days,
        "tier": args.tier or ("%dd" % args.ttl_days),
        "title": args.title, "images": images,
    })
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
