#!/usr/bin/env python3
"""Pin already-published example sites so the expiry sweep skips them.

New examples don't need this: publish them with build-site.py --pin. This is
for records published before --pin existed. For each sub it reads site:<sub>
from KV, sets pinned:true, writes the record back with the key metadata the
sweep reads, and swaps an old-style countdown badge for an "Example page"
badge.

Usage: pin-examples.py [sub ...]   (defaults to the 8 theme subs)
"""

import json
import re
import sys
import time

from mayfly_ops import CF_BASE, THEMES, cf, cf_token, curl, kv_url, load_env

OLD_BADGE = re.compile(r'<div class="badge" id="expiry" data-expires="[^"]*">.*?</div>', re.S)
NEW_BADGE = '<div class="badge" id="expiry" data-expires=""><strong>Example page · made with Mayfly</strong></div>'


def main():
    env = load_env()
    for sub in sys.argv[1:] or THEMES:
        key = "site:" + sub
        rec = None
        for _ in range(6):  # KV is eventually consistent right after a publish
            code, text = curl("GET", CF_BASE + kv_url(key, env), headers={"Authorization": "Bearer " + cf_token()})
            if code == 200:
                rec = json.loads(text)
                break
            time.sleep(20)
        if not rec or not rec.get("html"):
            print("FAILED to read", key)
            continue
        rec["pinned"] = True
        rec["html"] = OLD_BADGE.sub(NEW_BADGE, rec["html"])
        meta = json.dumps({"exp": rec.get("expiresAt", 0), "pinned": True})
        res = cf("PUT", kv_url(key, env), form=[("value", json.dumps(rec).encode()), ("metadata", meta)])
        print(("pinned " if res.get("success") else "WRITE FAILED ") + key)


if __name__ == "__main__":
    main()
