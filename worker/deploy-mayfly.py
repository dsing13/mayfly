#!/usr/bin/env python3
"""Deploy the Mayfly router Worker via the Cloudflare v4 REST API.

Creates the mayfly-sites KV namespace, uploads mayfly-router.js with the
KV binding, sets the ADMIN_TOKEN secret, installs a daily expiry sweep,
and uploads the landing page (site/index.html) if present.

Usage: deploy-mayfly.py [--upload-landing]
Domain attachment (after David buys the domain) is attach-domain.py.
"""
import json
import os
import secrets
import sys
import urllib.request
import uuid

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

CREDENTIAL = "custom.cloudflare"
ALLOWED = ["api.cloudflare.com"]
ACCOUNT = "2e7e19a2b269db15edd76c98799515bd"
BASE = "https://api.cloudflare.com/client/v4"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENV_PATH = os.path.join(ROOT, "hidden_files", "mayfly.env")
SCRIPT_NAME = "mayfly-router"
KV_TITLE = "mayfly-sites"


def cf_req(method, path, body=None, raw_body=None, content_type="application/json"):
    req = urllib.request.Request(BASE + path, method=method)
    add_surrogate_to_request(req, CREDENTIAL, entry_name="access_token",
                             allowed_hosts=ALLOWED)
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", content_type)
        req.data = data
    elif raw_body is not None:
        req.add_header("Content-Type", content_type)
        req.data = raw_body
    with urllib.request.urlopen(req, timeout=120) as resp:
        return read_json_response(resp)


def load_env():
    env = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    if "MAYFLY_ADMIN_TOKEN" not in env:
        env["MAYFLY_ADMIN_TOKEN"] = secrets.token_urlsafe(32)
        os.makedirs(os.path.dirname(ENV_PATH), exist_ok=True)
        with open(ENV_PATH, "w") as f:
            f.write("MAYFLY_ADMIN_TOKEN=%s\n" % env["MAYFLY_ADMIN_TOKEN"])
        os.chmod(ENV_PATH, 0o600)
        print("generated new MAYFLY_ADMIN_TOKEN")
    return env


def ensure_kv():
    res = cf_req("GET", "/accounts/%s/storage/kv/namespaces?per_page=100" % ACCOUNT)
    for ns in res.get("result", []):
        if ns["title"] == KV_TITLE:
            print("kv ok:", ns["id"])
            return ns["id"]
    res = cf_req("POST", "/accounts/%s/storage/kv/namespaces" % ACCOUNT,
                 {"title": KV_TITLE})
    nsid = res["result"]["id"]
    print("kv created:", nsid)
    return nsid


def upload_worker(kv_id):
    with open(os.path.join(HERE, "mayfly-router.js"), "rb") as f:
        src = f.read()
    metadata = {
        "main_module": "mayfly-router.js",
        "compatibility_date": "2026-09-01",
        "workers_dev": True,
        "bindings": [{"type": "kv_namespace", "name": "SITES", "namespace_id": kv_id}],
    }
    boundary = uuid.uuid4().hex
    parts = []
    parts.append(('--%s\r\nContent-Disposition: form-data; name="metadata"\r\n'
                  'Content-Type: application/json\r\n\r\n%s\r\n'
                  % (boundary, json.dumps(metadata))).encode())
    parts.append(('--%s\r\nContent-Disposition: form-data; name="script"; filename="mayfly-router.js"\r\n'
                  'Content-Type: application/javascript+module\r\n\r\n' % boundary).encode() + src + b'\r\n')
    parts.append(('--%s--\r\n' % boundary).encode())
    body = b"".join(parts)
    res = cf_req("PUT", "/accounts/%s/workers/scripts/%s" % (ACCOUNT, SCRIPT_NAME),
                 raw_body=body,
                 content_type="multipart/form-data; boundary=%s" % boundary)
    if not res.get("success"):
        print("WORKER UPLOAD FAILED:", res.get("errors"))
        sys.exit(1)
    print("worker uploaded:", SCRIPT_NAME)


def set_secret(token):
    res = cf_req("PUT", "/accounts/%s/workers/scripts/%s/secrets" % (ACCOUNT, SCRIPT_NAME),
                 {"name": "ADMIN_TOKEN", "text": token, "type": "secret_text"})
    if not res.get("success"):
        print("SECRET FAILED:", res.get("errors"))
        sys.exit(1)
    print("secret ADMIN_TOKEN set")


def set_schedule():
    # Daily sweep at ~04:17 ET for expired sites.
    res = cf_req("PUT", "/accounts/%s/workers/scripts/%s/schedules" % (ACCOUNT, SCRIPT_NAME),
                 [{"cron": "17 9 * * *"}])
    if not res.get("success"):
        print("SCHEDULE FAILED:", res.get("errors"))
        sys.exit(1)
    print("daily expiry sweep scheduled")


def put_kv(kv_id, key, data, content_type="text/html; charset=utf-8"):
    req = urllib.request.Request(
        "%s/accounts/%s/storage/kv/namespaces/%s/values/%s"
        % (BASE, ACCOUNT, kv_id, key), method="PUT")
    add_surrogate_to_request(req, CREDENTIAL, entry_name="access_token",
                             allowed_hosts=ALLOWED)
    req.add_header("Content-Type", content_type)
    req.data = data if isinstance(data, bytes) else data.encode()
    with urllib.request.urlopen(req, timeout=120) as resp:
        read_json_response(resp)
    print("kv put:", key)


def main():
    env = load_env()
    kv_id = ensure_kv()
    with open(ENV_PATH, "a") as f:
        pass
    # persist kv id alongside token
    lines = open(ENV_PATH).read().splitlines()
    if not any(l.startswith("MAYFLY_KV_ID=") for l in lines):
        with open(ENV_PATH, "a") as f:
            f.write("MAYFLY_KV_ID=%s\n" % kv_id)
    upload_worker(kv_id)
    set_secret(env["MAYFLY_ADMIN_TOKEN"])
    set_schedule()
    landing = os.path.join(ROOT, "site", "index.html")
    if os.path.exists(landing):
        with open(landing) as f:
            put_kv(kv_id, "page:_landing", f.read())
    else:
        print("no site/index.html yet — landing not uploaded")
    print("done. Test: https://%s.<account>.workers.dev/api/health" % SCRIPT_NAME)
    try:
        sd = cf_req("GET", "/accounts/%s/workers/subdomain" % ACCOUNT)
        sub = sd.get("result", {}).get("subdomain")
        if sub:
            url = "https://%s.%s.workers.dev" % (SCRIPT_NAME, sub)
            lines = open(ENV_PATH).read().splitlines()
            lines = [l for l in lines if not l.startswith("MAYFLY_WORKER_URL=")]
            lines.append("MAYFLY_WORKER_URL=%s" % url)
            with open(ENV_PATH, "w") as f:
                f.write("\n".join(lines) + "\n")
            os.chmod(ENV_PATH, 0o600)
            print("worker url:", url)
    except Exception as e:
        print("subdomain lookup failed:", e)


if __name__ == "__main__":
    main()
