#!/usr/bin/env python3
"""Attach a purchased domain to the Mayfly worker (run AFTER David buys it).

The domain must already delegate to Cloudflare nameservers (Porkbun NS switch,
as with raleighparkphotos.com). This script finds/creates the zone and adds a
wildcard route *.domain/* -> mayfly-router, then uploads nothing else.

Usage: attach-domain.py <domain>
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

CREDENTIAL = "custom.cloudflare"
ALLOWED = ["api.cloudflare.com"]
ACCOUNT = "2e7e19a2b269db15edd76c98799515bd"
BASE = "https://api.cloudflare.com/client/v4"
SCRIPT_NAME = "mayfly-router"


def cf_req(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    add_surrogate_to_request(req, CREDENTIAL, entry_name="access_token",
                             allowed_hosts=ALLOWED)
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
        req.data = data
    with urllib.request.urlopen(req, timeout=60) as resp:
        return read_json_response(resp)


def main():
    domain = sys.argv[1].lower().strip() if len(sys.argv) > 1 else ""
    if not domain or "." not in domain:
        print("usage: attach-domain.py <domain>")
        sys.exit(1)
    zones = cf_req("GET", "/zones?name=%s&account.id=%s" % (domain, ACCOUNT))
    results = zones.get("result", [])
    if results:
        zone = results[0]
        print("zone exists:", zone["id"], zone["status"])
    else:
        z = cf_req("POST", "/zones", {"name": domain, "account": {"id": ACCOUNT}})
        if not z.get("success"):
            print("ZONE CREATE FAILED:", z.get("errors"))
            print("Is the domain delegating to Cloudflare nameservers yet?")
            sys.exit(1)
        zone = z["result"]
        print("zone created:", zone["id"], "- status:", zone["status"])
        print("nameservers:", ", ".join(zone.get("name_servers", [])))
    zid = zone["id"]
    existing = cf_req("GET", "/zones/%s/workers/routes?per_page=100" % zid)
    have = {(r["pattern"], r["script"]) for r in existing.get("result", [])}
    pattern = "*.%s/*" % domain
    if (pattern, SCRIPT_NAME) in have:
        print("route ok:", pattern)
    else:
        res = cf_req("POST", "/zones/%s/workers/routes" % zid,
                     {"pattern": pattern, "script": SCRIPT_NAME})
        if res.get("success"):
            print("route created:", pattern)
        else:
            print("ROUTE FAILED:", res.get("errors"))
            sys.exit(1)
    # Apex serves the landing page too.
    pattern2 = "%s/*" % domain
    if (pattern2, SCRIPT_NAME) not in have:
        res = cf_req("POST", "/zones/%s/workers/routes" % zid,
                     {"pattern": pattern2, "script": SCRIPT_NAME})
        print(("route created: " if res.get("success") else "ROUTE FAILED: ") + pattern2)
    print("done. https://%s/ should serve Mayfly once DNS propagates." % domain)


if __name__ == "__main__":
    main()
