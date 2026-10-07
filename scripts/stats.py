#!/usr/bin/env python3
"""Mayfly traffic and order stats from Workers Analytics Engine.

The worker writes one data point per page view and per chat/order event to
the mayfly_events dataset. Nothing in it identifies a person: no IPs, no
cookies, no user IDs. "Visitors" are counted with a hash that changes every
UTC day, so the same person on two days counts twice, and nobody can be
followed across days or across sites.

Usage: stats.py [--days 7]
Needs a Cloudflare API token with Account Analytics: Read (CLOUDFLARE_API_TOKEN).
"""

import argparse
import sys

from mayfly_ops import ACCOUNT, cf

DATASET = "mayfly_events"


def sql(query):
    res = cf("POST", "/accounts/%s/analytics_engine/sql" % ACCOUNT, raw=query, content_type="text/plain")
    if "data" not in res:
        sys.exit("query failed: %s\n(the token needs Account Analytics: Read)" % (res.get("errors") or res))
    return res["data"]


def table(title, rows, cols):
    print("\n" + title)
    if not rows:
        print("  (none)")
        return
    widths = [max(len(str(c)), *(len(str(r.get(c, ""))) for r in rows)) for c in cols]
    print("  " + "  ".join(str(c).ljust(w) for c, w in zip(cols, widths)))
    for r in rows:
        print("  " + "  ".join(str(r.get(c, "")).ljust(w) for c, w in zip(cols, widths)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=7)
    days = ap.parse_args().days
    since = "timestamp > NOW() - INTERVAL '%d' DAY" % days
    humans = "blob6 != 'bot'"
    n = "SUM(_sample_interval)"

    print("Mayfly, last %d days" % days)

    ev = {
        r["event"]: r
        for r in sql(
            "SELECT blob1 AS event, %s AS n, SUM(_sample_interval * double2) AS usd FROM %s "
            "WHERE %s AND %s GROUP BY event" % (n, DATASET, since, humans)
        )
    }
    land = sql(
        "SELECT %s AS n FROM %s WHERE %s AND %s AND blob1 = 'view' AND blob2 = 'landing'" % (n, DATASET, since, humans)
    )
    start = sql(
        "SELECT %s AS n FROM %s WHERE %s AND %s AND blob1 = 'view' AND blob2 = 'start'" % (n, DATASET, since, humans)
    )
    def get(rows):
        return int(float(rows[0]["n"])) if rows and rows[0].get("n") is not None else 0

    def num(k):
        return int(float(ev.get(k, {}).get("n", 0) or 0))

    funnel = [
        {"step": "Landing page views", "count": get(land)},
        {"step": "Chat page views", "count": get(start)},
        {"step": "Chats started", "count": num("chat_start")},
        {"step": "Orders", "count": num("order")},
        {"step": "Marked paid", "count": 0},
    ]
    paid = sql(
        "SELECT %s AS n, SUM(_sample_interval * double2) AS usd FROM %s WHERE %s AND blob1 = 'order_status' "
        "AND blob10 = 'paid'" % (n, DATASET, since)
    )
    funnel[-1]["count"] = get(paid)
    table("Funnel", funnel, ["step", "count"])
    usd = float(ev.get("order", {}).get("usd", 0) or 0)
    paid_usd = float(paid[0]["usd"]) if paid and paid[0].get("usd") else 0.0
    print("  order value (if all paid): $%.2f   marked paid: $%.2f" % (usd, paid_usd))

    views = sql(
        "SELECT blob2 AS site, %s AS views FROM %s WHERE %s AND %s AND blob1 = 'view' "
        "GROUP BY site ORDER BY views DESC LIMIT 25" % (n, DATASET, since, humans)
    )
    pairs = sql(
        "SELECT blob2 AS site, blob9 AS v FROM %s WHERE %s AND %s AND blob1 = 'view' AND blob9 != '' "
        "GROUP BY site, v LIMIT 20000" % (DATASET, since, humans)
    )
    uniq = {}
    for p in pairs:
        uniq[p["site"]] = uniq.get(p["site"], 0) + 1
    for r in views:
        r["views"] = int(float(r["views"]))
        r["visitor-days"] = uniq.get(r["site"], 0)
    table("Page views (sites, landing, chat)", views, ["site", "views", "visitor-days"])

    orders = sql(
        "SELECT blob7 AS theme, blob8 AS tier, %s AS orders FROM %s WHERE %s AND blob1 = 'order' "
        "GROUP BY theme, tier ORDER BY orders DESC" % (n, DATASET, since)
    )
    table("Orders by design and lifespan", orders, ["theme", "tier", "orders"])

    refs = sql(
        "SELECT blob5 AS referrer, %s AS views FROM %s WHERE %s AND %s AND blob1 = 'view' AND blob5 != '' "
        "GROUP BY referrer ORDER BY views DESC LIMIT 15" % (n, DATASET, since, humans)
    )
    table("Where visitors came from", refs, ["referrer", "views"])

    where = sql(
        "SELECT blob4 AS country, blob6 AS device, %s AS views FROM %s WHERE %s AND blob1 = 'view' "
        "GROUP BY country, device ORDER BY views DESC LIMIT 15" % (n, DATASET, since)
    )
    table("Country and device (bots included)", where, ["country", "device", "views"])

    probs = [
        {"event": k, "count": num(k)}
        for k in ("ai_error", "rate_limited", "chat_rejected", "chat_unclear", "expired_hit", "missing", "error")
        if num(k)
    ]
    table("Problems and edge cases", probs, ["event", "count"])


if __name__ == "__main__":
    main()
