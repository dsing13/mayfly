"""Shared helpers for the Mayfly ops scripts.

Credentials, in order of preference:
  1. The hatch VM's dynamic_credentials surrogate (custom.cloudflare), when
     that module is importable.
  2. CLOUDFLARE_API_TOKEN from the environment.
  3. CLOUDFLARE_API_TOKEN in hidden_files/mayfly.env.

All HTTP goes through curl: Python's urllib has been flaky against the
Cloudflare edge from the hatch VM's egress proxy, and curl works everywhere.
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENV_PATH = os.path.join(ROOT, "hidden_files", "mayfly.env")
ACCOUNT = "2e7e19a2b269db15edd76c98799515bd"
CF_BASE = "https://api.cloudflare.com/client/v4"
APEX = os.environ.get("MAYFLY_APEX", "trymayfly.com")
THEMES = ["celebrate", "invite", "announce", "sell", "remember", "rally", "inform", "play"]
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def load_env(required=True):
    env = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    elif required:
        sys.exit("missing %s (copy it from secure storage; it is git-ignored)" % ENV_PATH)
    return env


def save_env_value(key, value):
    lines = []
    if os.path.exists(ENV_PATH):
        lines = [ln for ln in open(ENV_PATH).read().splitlines() if not ln.startswith(key + "=")]
    lines.append("%s=%s" % (key, value))
    os.makedirs(os.path.dirname(ENV_PATH), exist_ok=True)
    with open(ENV_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(ENV_PATH, 0o600)


def cf_token():
    try:
        sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
        from dynamic_credentials import dynamic_credential_entry  # hatch VM only

        return str(dynamic_credential_entry("custom.cloudflare", "access_token")["surrogate"]).strip()
    except Exception:
        pass
    tok = os.environ.get("CLOUDFLARE_API_TOKEN") or load_env(required=False).get("CLOUDFLARE_API_TOKEN")
    if not tok:
        sys.exit(
            "No Cloudflare credentials. Set CLOUDFLARE_API_TOKEN (Workers Scripts, "
            "Workers KV, Workers Routes, Zone, and Account Analytics permissions)."
        )
    return tok


def curl(method, url, headers=None, data=None, form=None, timeout=120):
    """Run curl and return (status_code, body_text).

    form: list of (name, value). bytes values are sent from a temp file;
    str values go through --form-string, so ; and @ in them stay literal.
    """
    cmd = ["curl", "-sS", "--max-time", str(timeout), "-X", method, "-A", BROWSER_UA, "-w", "\n%{http_code}"]
    for k, v in (headers or {}).items():
        cmd += ["-H", "%s: %s" % (k, v)]
    tmps = []

    def tmpfile(payload):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, "wb") as f:
            f.write(payload if isinstance(payload, bytes) else payload.encode())
        tmps.append(path)
        return path

    try:
        if data is not None:
            cmd += ["--data-binary", "@" + tmpfile(data)]
        for name, val in form or []:
            if isinstance(val, bytes):
                cmd += ["-F", "%s=<%s" % (name, tmpfile(val))]
            else:
                cmd += ["--form-string", "%s=%s" % (name, val)]
        cmd.append(url)
        out = subprocess.run(cmd, capture_output=True)
    finally:
        for path in tmps:
            os.unlink(path)
    if out.returncode != 0:
        raise RuntimeError("curl failed: %s" % out.stderr.decode(errors="replace").strip())
    body, _, code = out.stdout.decode(errors="replace").rpartition("\n")
    return int(code or 0), body


def cf(method, path, body=None, raw=None, content_type="application/json", form=None):
    """Call the Cloudflare v4 API. Returns parsed JSON (or {} on empty body)."""
    headers = {"Authorization": "Bearer " + cf_token()}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body)
    elif raw is not None:
        headers["Content-Type"] = content_type
        data = raw
    code, text = curl(method, CF_BASE + path, headers=headers, data=data, form=form)
    try:
        return json.loads(text) if text.strip() else {}
    except ValueError:
        return {"success": False, "errors": [{"code": code, "message": text[:300]}]}


def kv_id(env=None):
    env = env or load_env()
    if "MAYFLY_KV_ID" not in env:
        sys.exit("MAYFLY_KV_ID missing from %s (run worker/deploy-mayfly.py once)" % ENV_PATH)
    return env["MAYFLY_KV_ID"]


def kv_url(key, env=None):
    from urllib.parse import quote

    return "/accounts/%s/storage/kv/namespaces/%s/values/%s" % (ACCOUNT, kv_id(env), quote(key, safe=""))


def worker_url(env):
    return (env.get("MAYFLY_WORKER_URL") or "https://" + APEX).rstrip("/")


def admin_api(env, method, path, body=None):
    """Call the worker's admin API with the Bearer token."""
    headers = {"Authorization": "Bearer " + env["MAYFLY_ADMIN_TOKEN"]}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body)
    code, text = curl(method, worker_url(env) + path, headers=headers, data=data)
    try:
        return json.loads(text)
    except ValueError:
        return {"ok": False, "status": code, "error": text[:300]}
