#!/usr/bin/env python3
"""Deploy the Mayfly router Worker via the Cloudflare v4 REST API.

Creates the mayfly-sites KV namespace if needed, uploads mayfly-router.js
with all of its bindings (KV, Workers AI, Analytics Engine), sets the
ADMIN_TOKEN secret, installs the daily expiry sweep, and uploads the landing
page, the chat page, and the landing-page images.

Every upload replaces the Worker's whole binding list, so every binding the
code uses must be listed here. (An earlier version of this script listed
only KV; re-running it would have dropped the AI binding and broken /start.)

Usage:
  deploy-mayfly.py                 worker + pages + images
  deploy-mayfly.py --pages-only    just site/index.html, site/start.html, site/img/
  deploy-mayfly.py --no-analytics  skip the Analytics Engine binding
Domain attachment is attach-domain.py.
"""

import argparse
import json
import mimetypes
import os
import secrets
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from mayfly_ops import ACCOUNT, ROOT, cf, kv_url, load_env, save_env_value  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT_NAME = "mayfly-router"
KV_TITLE = "mayfly-sites"
ANALYTICS_DATASET = "mayfly_events"


def ensure_token(env):
    if "MAYFLY_ADMIN_TOKEN" not in env:
        env["MAYFLY_ADMIN_TOKEN"] = secrets.token_urlsafe(32)
        save_env_value("MAYFLY_ADMIN_TOKEN", env["MAYFLY_ADMIN_TOKEN"])
        print("generated new MAYFLY_ADMIN_TOKEN")


def ensure_kv(env):
    if env.get("MAYFLY_KV_ID"):
        return env["MAYFLY_KV_ID"]
    res = cf("GET", "/accounts/%s/storage/kv/namespaces?per_page=100" % ACCOUNT)
    for ns in res.get("result", []):
        if ns["title"] == KV_TITLE:
            nsid = ns["id"]
            break
    else:
        res = cf("POST", "/accounts/%s/storage/kv/namespaces" % ACCOUNT, {"title": KV_TITLE})
        nsid = res["result"]["id"]
        print("kv created:", nsid)
    save_env_value("MAYFLY_KV_ID", nsid)
    env["MAYFLY_KV_ID"] = nsid
    return nsid


def upload_worker(kv_id, analytics):
    with open(os.path.join(HERE, "mayfly-router.js"), "rb") as f:
        src = f.read()
    bindings = [
        {"type": "kv_namespace", "name": "SITES", "namespace_id": kv_id},
        {"type": "ai", "name": "AI"},
    ]
    if analytics:
        bindings.append({"type": "analytics_engine", "name": "EVENTS", "dataset": ANALYTICS_DATASET})
    metadata = {
        "main_module": "mayfly-router.js",
        "compatibility_date": "2026-09-01",
        "workers_dev": True,
        "bindings": bindings,
        "keep_bindings": ["secret_text"],
    }
    boundary = uuid.uuid4().hex
    body = b"".join(
        [
            (
                '--%s\r\nContent-Disposition: form-data; name="metadata"\r\n'
                "Content-Type: application/json\r\n\r\n%s\r\n" % (boundary, json.dumps(metadata))
            ).encode(),
            (
                '--%s\r\nContent-Disposition: form-data; name="script"; filename="mayfly-router.js"\r\n'
                "Content-Type: application/javascript+module\r\n\r\n" % boundary
            ).encode()
            + src
            + b"\r\n",
            ("--%s--\r\n" % boundary).encode(),
        ]
    )
    res = cf(
        "PUT",
        "/accounts/%s/workers/scripts/%s" % (ACCOUNT, SCRIPT_NAME),
        raw=body,
        content_type="multipart/form-data; boundary=%s" % boundary,
    )
    if not res.get("success"):
        sys.exit(
            "WORKER UPLOAD FAILED: %s\n(If the error mentions analytics_engine, "
            "re-run with --no-analytics.)" % res.get("errors")
        )
    print("worker uploaded:", SCRIPT_NAME, "bindings:", ", ".join(b["name"] for b in bindings))


def set_secret(token):
    res = cf(
        "PUT",
        "/accounts/%s/workers/scripts/%s/secrets" % (ACCOUNT, SCRIPT_NAME),
        {"name": "ADMIN_TOKEN", "text": token, "type": "secret_text"},
    )
    if not res.get("success"):
        sys.exit("SECRET FAILED: %s" % res.get("errors"))
    print("secret ADMIN_TOKEN set")


def set_schedule():
    # Daily sweep at ~05:17 ET for expired sites.
    res = cf("PUT", "/accounts/%s/workers/scripts/%s/schedules" % (ACCOUNT, SCRIPT_NAME), [{"cron": "17 9 * * *"}])
    if not res.get("success"):
        sys.exit("SCHEDULE FAILED: %s" % res.get("errors"))
    print("daily expiry sweep scheduled")


def put_kv(env, key, data, metadata=None):
    payload = data if isinstance(data, bytes) else data.encode()
    form = [("value", payload)]
    if metadata is not None:
        form.append(("metadata", json.dumps(metadata)))
    res = cf("PUT", kv_url(key, env), form=form)
    if not res.get("success"):
        sys.exit("KV PUT FAILED %s: %s" % (key, res.get("errors")))
    print("kv put:", key, "(%d KB)" % (len(payload) // 1024))


def upload_pages(env):
    for src, key in (("index.html", "page:_landing"), ("start.html", "page:_start")):
        path = os.path.join(ROOT, "site", src)
        with open(path, encoding="utf-8") as f:
            put_kv(env, key, f.read())
    # Landing-page images: served at /img/<file> from KV img:mayfly/<file> ("mayfly" is a reserved sub).
    imgdir = os.path.join(ROOT, "site", "img")
    if os.path.isdir(imgdir):
        for fn in sorted(os.listdir(imgdir)):
            ct = {".webp": "image/webp", ".avif": "image/avif"}.get(os.path.splitext(fn)[1].lower()) \
                or mimetypes.guess_type(fn)[0]
            if ct not in ("image/jpeg", "image/png", "image/webp", "image/avif"):
                continue
            with open(os.path.join(imgdir, fn), "rb") as f:
                put_kv(env, "img:mayfly/" + fn, f.read(), {"ct": ct, "exp": 0})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pages-only", action="store_true")
    ap.add_argument("--no-analytics", action="store_true")
    args = ap.parse_args()

    env = load_env(required=False)
    kv = ensure_kv(env)
    if not args.pages_only:
        ensure_token(env)
        upload_worker(kv, analytics=not args.no_analytics)
        set_secret(env["MAYFLY_ADMIN_TOKEN"])
        set_schedule()
    upload_pages(env)
    print("done. Check: curl -s https://trymayfly.com/api/health")


if __name__ == "__main__":
    main()
