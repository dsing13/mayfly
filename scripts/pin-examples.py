#!/usr/bin/env python3
"""Pin the 8 Mayfly example sites so the daily expiry sweep skips them.

For each theme sub:
  1. Read site:<sub> from KV (with retries — KV is eventually consistent).
  2. Set pinned:true on the record.
  3. Swap the countdown badge for a "permanent example" badge
     (data-expires="" -> the badge JS sees NaN and leaves the static text).
  4. Remove any <section> whose .gallery div is empty (no photos on examples).
  5. Write the record back.

Usage: python3 pin-examples.py [sub ...]   (defaults to all 8 themes)
"""
import json
import re
import subprocess
import sys
import time
import urllib.parse

THEMES = ["celebrate", "invite", "announce", "sell",
          "remember", "rally", "inform", "play"]
ACCOUNT = "2e7e19a2b269db15edd76c98799515bd"

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import dynamic_credential_entry  # noqa: E402


def kv_id():
    with open("/home/hatch/workspace/mayfly/hidden_files/mayfly.env") as f:
        for line in f:
            if line.startswith("MAYFLY_KV_ID="):
                return line.strip().split("=", 1)[1]
    raise RuntimeError("MAYFLY_KV_ID not found")


def kv_call(method, key, data=None):
    e = dynamic_credential_entry("custom.cloudflare", "access_token")
    token = str(e["surrogate"]).strip()
    url = ("https://api.cloudflare.com/client/v4/accounts/%s/storage/kv/"
           "namespaces/%s/values/%s"
           % (ACCOUNT, kv_id(), urllib.parse.quote(key, safe="")))
    cmd = ["curl", "-s", "--max-time", "60", "-X", method,
           "-H", "Authorization: Bearer " + token]
    if data is not None:
        cmd += ["-H", "Content-Type: application/json",
                "--data-binary", data]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout


PERM_BADGE = ('<div class="badge" id="expiry" data-expires="">'
              "<strong>permanent example · made with Mayfly</strong> 🪰</div>")


def patch_html(html):
    # 1. Swap the countdown badge for a permanent-example badge.
    html = re.sub(r'<div class="badge" id="expiry" data-expires="[^"]*">.*?</div>',
                  PERM_BADGE, html, flags=re.S)
    # 2. Drop any section whose gallery div is empty (no photos on examples).
    html = re.sub(r'<section\b[^>]*>(?:(?!</section>).)*'
                  r'<div class="gallery">\s*</div>'
                  r'(?:(?!</section>).)*</section>',
                  "", html, flags=re.S)
    return html


def main():
    subs = sys.argv[1:] or THEMES
    for sub in subs:
        key = "site:" + sub
        rec = None
        for attempt in range(6):
            out = kv_call("GET", key)
            try:
                rec = json.loads(out)
                break
            except Exception:
                time.sleep(20)
        if not rec or not rec.get("html"):
            print("FAILED to read", key)
            continue
        rec["pinned"] = True
        rec["html"] = patch_html(rec["html"])
        out = kv_call("PUT", key, json.dumps(rec))
        ok = '"success":true' in out
        print(("pinned " if ok else "WRITE FAILED ") + key,
              "| badge:" + ("ok" if "permanent example" in rec["html"] else "MISSING"),
              "| galleries removed:" + ("yes" if 'class="gallery"' not in rec["html"] else "no"))


if __name__ == "__main__":
    main()
