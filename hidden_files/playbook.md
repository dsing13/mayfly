# Mayfly — ops playbook

Ephemeral website service. Customer emails an idea → Nova asks follow-ups →
builds a one-page site from a theme → customer pays → site published at
`<sub>.<domain>` → evaporates after the purchased duration.

## Hardening pass (2026-10-07, branch `polish`)
What changed, and what to do after it merges. Details in README.md.
- **Deploy script now binds AI.** The old `deploy-mayfly.py` sent only the KV
  binding; re-running it would have dropped `AI` and broken /start. It now
  sends KV + AI + Analytics Engine (`EVENTS`, dataset `mayfly_events`) and
  uploads `site/start.html` and `site/img/` too. If the account rejects the
  Analytics Engine binding, run with `--no-analytics`.
- **Scripts run outside the hatch VM.** Shared helper `scripts/mayfly_ops.py`
  uses the hatch credential surrogate when present, else
  `CLOUDFLARE_API_TOKEN`. pin-examples.py no longer hardcodes /home/hatch.
- **Orders**: one `order:<id>` key each, status in key metadata; no more
  read-modify-write on `orders:pending` (two orders at once could drop one).
  `GET /api/orders/pending` returns the 50 most recent (it used to return the
  oldest 50, so order #51 onward was invisible), still reads the legacy list,
  and takes `?since=<ms>`. New `PATCH /api/orders/:id {status, sub?}`.
- **Order photos** are re-saved with a 30-day TTL when the order completes
  (they used to expire 24h after upload, before a slow build).
- **Stripe links** carry `?client_reference_id=<order id>`.
- **Rate limits** moved off KV (session record + edge cache): each chat
  message used to cost 2 extra KV writes against the 1,000/day free limit.
- **AI quota exhaustion** returns a clear "busy" message instead of an
  endless "try again".
- **Themes v4**: rebuilt on a shared base (`_widgets.html`, injector uses
  markers). Fixed: the expiry badge text was hardcoded per theme (its script
  was lost in an earlier injector run), the footer linked to mayfly.site
  (someone else's domain), the memorial theme showed a seconds countdown, and
  the hero card overlapped the countdown on phones. Section labels now have
  overridable defaults (`{{details_heading|The details}}`).
- **build-site.py**: rotates photos upright (EXIF), strips EXIF/GPS, hashed
  image names (cached forever), escapes non-HTML vars, fixes the
  double-escaped `<title>` (`&amp;ldquo;` in the remember example tab), adds
  link-preview tags, `--pin`, `--out` for local preview.
- **Example photos**: removed the mismatched ones (Star of David/barbed-wire
  memorial and yahrzeit candles on a Presbyterian memorial, three different
  couples on one wedding, two different dogs on the lost-dog page, a "5"
  balloon on a 7th birthday, a duplicate baby photo).
- **Landing page** redesigned with Unsplash photos (credits in
  `site/img-src/CREDITS.json`, regenerate with `scripts/build-landing-images.py`).

### After merge
1. `worker/deploy-mayfly.py` (worker, pages, images).
2. Rebuild each example on the new themes, pinned:
   `scripts/build-site.py --theme <t> --sub <t> --ttl-days 366 --pin --title "..." --vars examples/vars-<t>.json --images examples/photos/<t>/`
3. Give the Cloudflare token Account Analytics: Read, then `scripts/stats.py`.

## Infra (all live as of 2026-09-26)
- Worker `mayfly-router` (account 2e7e19a2b269db15edd76c98799515bd), uploaded
  via `worker/deploy-mayfly.py` (Cloudflare v4 REST + surrogate auth, same
  pattern as Frame's deploy-worker.py).
- KV namespace `mayfly-sites` (id in `hidden_files/mayfly.env`):
  `site:<sub>` → {html,title,tier,createdAt,expiresAt}; `img:<sub>/<file>` →
  image bytes; `page:_landing` → landing HTML.
- Daily expiry sweep: Worker scheduled trigger `17 9 * * *` (cron) deletes
  expired `site:` keys + their images. Expired hits also serve a 410
  "evaporated" page even before the sweep runs.
- Admin API: `POST /api/sites` {sub,html,ttlDays,tier,title,images[]},
  `GET /api/sites/:sub[?preview=1]`, `DELETE /api/sites/:sub`,
  `GET /api/health`. Auth: `Authorization: Bearer $MAYFLY_ADMIN_TOKEN`
  (in `hidden_files/mayfly.env`, mode 600).
- Intake inbox: `mayfly@agentmail.to` (AgentMail free tier, 1 of 3 inboxes used
  by david-6262; 1 slot left).
- Cron `mayfly-inbox-watch` (every 20m, goal-owned): triages new mail,
  watermark in goal hidden_files/mayfly-inbox-watermark.json.
- Themes: `site/themes/{celebrate,invite,announce,sell,remember,rally,inform,play}.html`
  — single-file, mobile-first, `{{placeholder}}` contract, live expiry countdown,
  "made with Mayfly" footer, QR placeholder. Landing: `site/index.html`
  (pricing deliberately TBD: "Final pricing lands at launch").
- **Theme widgets (2026-10-06 upgrade — David: "too simple, needs to be richer")**:
  shared block in `site/themes/_widgets.html`, injected by
  `scripts/inject-widgets.py` (idempotent; edit `_widgets.html` + re-run, never
  hand-edit injected copies). Vanilla JS, no libs, ~10KB/theme. Widgets:
  photo lightbox (tap any gallery/hero photo; swipe + arrows + Esc), event
  countdown (ticks each second), add-to-calendar (.ics data URI, 2h default),
  get-directions (Google Maps query link), RSVP yes/no buttons (prefilled
  mailto:/sms: from contact type), share button (navigator.share → clipboard
  fallback), details accordion (native `<details class="acc">` in vars HTML).
  Per-theme: celebrate/invite/rally/play = countdown+cal+dir+rsvp+share+lightbox;
  sell/remember = countdown+cal+dir+share+lightbox; inform = directions+big
  call/share+lightbox; announce = share+lightbox.
- New optional placeholders: `{{event_iso}}` (ISO datetime, drives countdown
  + calendar; past dates show "it's happening!" <24h or "that was a good one"),
  `{{venue_text}}` (directions query), `{{rsvp_contact}}` (email or phone).
  All widget blocks hide when their data is empty; old vars.json files still
  render (safety net in build-site.py wipes unreplaced `{{...}}`, now incl.
  digits — fixed `details2_html` leaking on 2026-10-06).
- Example photos: `examples/photos/<theme>/NN.jpg` (Wikimedia Commons, free
  license, hotlink-stable) → build-site.py `--images` maps to
  `/_img/<sub>/photo-N.jpg`. Always spot-check a contact sheet before
  publishing (AGENTS.md photo rule).
## Pricing (locked 2026-10-06, David approved; revised same day per David)
- Free — 1 day (24h). Full design, all themes, Mayfly badge. One per email.
  No payment; intake via the chat at trymayfly.com/start (email fallback).
- $1 — 2 days. https://buy.stripe.com/6oU00l6Ee7iu8Cn3300kE04 (plink_1UNdTyP3HLIpte9TcppcJ7Jz)
- $1.50 — 7 days (MODAL tier). https://buy.stripe.com/fZu6oJ8MmauGf0L6fc0kE05 (plink_1UNdU0P3HLIpte9TW56hRY3y)
- $5 — 1 month (30d). https://buy.stripe.com/5kQaEZ2nY5am2dZcDA0kE06 (plink_1UNdU1P3HLIpte9TPW4pgp0l)
- $50 — 1 year (365d). https://buy.stripe.com/bJefZjbYy1Ya3i38nk0kE07 (plink_1UNdU3P3HLIpte9TNw6Yrd1q)
- Old links ($1/wk, $12/mo, $29/3mo: plink_1UNaULP3HLIpte9TNzTT85JW, plink_1UNaUmP3HLIpte9T3ijiJ3I7, plink_1UNaUrP3HLIpte9Trvd3lYYh) DEACTIVATED 2026-10-06.
- Payment links live in the Frame Charlotte Stripe account (acct_1PQyJ7P3HLIpte9T,
  the only connected account) — move to a Mayfly account later if David wants.
  All redirect to https://trymayfly.com/#thanks after payment.
  Extensions at the same rates. build-site.py: --ttl-days 1/2/7/30/365 with
  --tier free/twoday/week/month/year. Worker TIERS set matches; chat prompt
  quotes the current ladder.
- Publish: `scripts/build-site.py --theme … --sub … --ttl-days … --vars vars.json [--images dir]`.

## Fulfillment flow (per order)
1. Inbox watch flags new mail → Nova reads it.
2. Content check: refuse lewd/vulgar/racist/dangerous/gross/vice. Otherwise reply
   with clarifying questions (theme, duration, photos, details).
3. Paid tiers: the chat already sent the Stripe link with the order id as
   client_reference_id. Match the payment in Stripe, then
   `PATCH /api/orders/<id> {"status":"paid"}`.
4. On payment: `build-site.py` → publish → email customer the URL →
   `PATCH /api/orders/<id> {"status":"built","sub":"<sub>"}`.
5. Site evaporates automatically. Offer renewal before expiry (manual for now).

## Domain (PENDING — David's move)
Available as of 2026-09-26 (DNS NXDOMAIN): trymayfly.com, heymayfly.com,
mayflysite.com, usemayfly.com, getmayfly.site, mayfly.link, mayflydays.com.
Taken: mayfly.site, getmayfly.com, mayfly.page, mayflyday.com, mayflyweb.com.
After purchase: delegate nameservers to Cloudflare (Porkbun NS switch, as with
raleighparkphotos.com), then run `worker/attach-domain.py <domain>` — creates
the zone if needed, adds `*.domain/*` + `domain/*` routes to mayfly-router.
Then update the landing page CTA email to the real domain.

## Chat intake (LIVE 2026-10-06)
- **https://trymayfly.com/start** — conversational intake chat (Nova, powered by
  Workers AI). Page HTML in KV `page:_start` (source: `site/start.html`);
  served by the worker's `/start` route. Email intake (mayfly@agentmail.to)
  stays as fallback link on the page.
- Endpoints (public, no admin auth): `POST /api/intake/chat` {sessionId, message}
  and `POST /api/intake/upload` {sessionId, name, ct, b64}. Light IP rate limit
  (60 chat msgs/hour). Sessions in KV `intake:<sid>` (24h TTL).
- **Models** (Workers AI, free tier): chat `@cf/meta/llama-3.1-8b-instruct-fp8`;
  text moderation Llama Guard `@cf/meta/llama-guard-3-8b` + house-policy
  classifier prompt on the instruct model (Llama Guard alone does NOT catch
  vice — keg-party test passed Guard, caught by layer 2); image moderation
  `@cf/meta/llama-3.2-11b-vision-instruct` (license agreement accepted via API
  2026-10-06; fail-closed on any AI error).
- Bot collects: occasion → theme guess (8 themes), who/what/when/where, tone,
  tier (free/week/month/quarter locked), then the customer's **email address**
  (added 2026-10-06 — needed so fulfillment can deliver the site link). One
  question/reply, <40 words, ~6 exchanges, then summary + confirm. On confirm:
  KV `order:<sid>`
  {theme,details,tone,tier,email,images[],createdAt,status:'pending'} and sid
  appended to `orders:pending` (JSON array) for the inbox-watch fulfillment
  flow. Nothing auto-publishes, no emails sent.
- **Admin endpoint** `GET /api/orders/pending` (Bearer admin token) returns
  {count, orders[]} with full order records — used by the mayfly-inbox-watch
  cron (checks orders against `mayfly-orders-watermark.json`).
- **Uploads go to KV, NOT R2** (`intake:<sid>/<file>`, 5MB/file, 6/session):
  R2 is not enabled on this account and can only be enabled via the Cloudflare
  dashboard (API returns 10042). If David ever wants R2: enable in dashboard,
  then repoint handleIntakeUpload to an R2 binding.
- Worker bindings now: `SITES` (kv_namespace) + `AI` (Workers AI). Redeploy via
  curl multipart PUT (script: /tmp/deploy-intake.py — move to workspace if
  reused; urllib is flaky vs api.cloudflare.com, use curl + dynamic_credentials
  surrogate).
- **Deterministic interview (2026-10-06, David: "ask those every time deterministically")**:
  `REQUIRED` map in the worker lists the minimum facts per theme (celebrate:
  occasion/datetime/location/host; invite: event/datetime/venue/rsvp; announce:
  subject/date/facts; sell: items/location/contact; remember: name/dates/service;
  rally: cause/meetup/contact; inform: subject/keyfacts/contact; play:
  activity/when/howtojoin). The system prompt carries the same checklist, but the
  WORKER enforces it: `checkOrderComplete()` rejects any order JSON missing a
  required field (or email, tier, details, or photos≠none with zero uploads) and
  nudges the model to ask for the next missing item — the interview cannot end
  early. Photos are asked for every time (min 1, push for 3+). Order records now
  include a `fields` object with the required facts.
- QA'd 2026-10-06: sparse answers → model asked for every sell field; early
  finalize attempt → worker refused and sent it back for missing items. Test keys
  cleaned up.
- **Moderation fixes 2026-10-06 (found by QA)**: (1) Llama Guard flagged street
  addresses as S7/privacy and killed sessions — but addresses are REQUIRED fields.
  Fix: if Guard's ONLY category is S7, defer to the house-policy layer (which
  passes plain addresses); fail closed on anything else. Every order is still
  human-reviewed before building. (2) Rejection is now sticky via a separate
  `rejected:<sid>` KV marker (never overwritten) checked before session load —
  previously a stale KV read could resurrect a rejected session (KV is
  eventually consistent). Verified: address passes, keg-party msg still
  rejected, rejected session stays rejected.
- **Chat UX fixes 2026-10-06 (David: "This sucks" — screenshot of a real session)**:
  (1) Moderation is now typo-tolerant and 3-way (OK/UNCLEAR/REJECT) — "shat"
  (typo for chat) no longer nukes a nearly-done order; UNCLEAR steers back warmly
  without killing the session. (2) The bot no longer narrates its checklist
  ("already collected", "required info") — human-talk rules in the system prompt.
  (3) The journey is now explicit: the /start greeting explains the steps
  (questions → duration → payment → link by email within a few hours), and the
  completion reply says what happens next + names the email. Paid tiers get
  their Stripe payment link (clickable — bot replies are linkified) right in
  the completion message. (4) Worker-side structured state: every turn runs a
  transient extraction call into `sess.collected`; an "[system: facts already
  gathered]" note is injected into the prompt so the model stops re-asking, and
  `mergeCollected()` fills the final order JSON from worker state before the
  deterministic gate. Field aliases accepted (seller/host→contact,
  venue/address→location). (5) Raw-JSON leak fixed: if the model's order blob
  is malformed, a repair re-asks with 320 tokens; a final guard guarantees a raw
  blob never reaches the user. Verified end-to-end: paid order completed with
  the $1.50 Stripe link in the reply and a clean order record. QA keys cleaned.
- **Robustness pass 2026-10-06 (David: "Not great" — every message failed with
  the generic error)**: root cause was the sticky rejection marker meeting a
  reused session ID — his phone kept the rejected session from the "shat" chat,
  so every message returned `session rejected` with no recovery path. Fixes:
  (1) frontend auto-starts a fresh session on any dead-session error
  ("Let's start fresh…") instead of dead-ending; (2) AI screens now run in
  parallel waves (Guard+policy together, extract+reply together) instead of 4
  sequential calls — same call count, ~half the wall-clock; (3) the reply
  auto-retries once on transient AI failures, and the frontend retries once on
  network blips; (4) rate limiting moved from per-IP to per-session (carrier
  NAT shares one IP across many phones — per-IP false-triggered); (5) fixed
  stale TIER_CHIPS still showing the old $1/$12/$29 ladder — now match live
  pricing. Verified: normal/typo/vice behavior unchanged, new page JS live.
- **False-rejection root cause 2026-10-06 (David: "this is unusable" — "lets giddy
  up" killed a wedding order)**: the Workers AI free daily allocation (10,000
  neurons/day) was exhausted by QA + testing, and every moderation call
  fail-closed its *infrastructure* errors into REJECT — so "AI is down" looked
  exactly like "user is bad" and sessions died. Fixes: (1) AI infra errors now
  throw through moderation and return a retryable "ai hiccup" error — the
  session is never killed for an outage; (2) a lone policy REJECT is confirmed
  with a second independent judgment — only a double-REJECT kills the session
  (single small-model flakes become a warm steer); (3) garbled classifier
  output is lenient (every order is human-reviewed before building); (4) a
  violating photo now rejects just the upload, not the whole session;
  (5) POLICY_PROMPT requires high confidence for REJECT. Usage trims:
  extraction window 14→8 msgs, history 24→16, extract 220→150 tokens.
  Pricing note: beyond 10k neurons/day it's $0.011/1k on Workers Paid
  ($5/mo base) — free tier likely fine until real order volume; revisit then.
- **Session recovery 2026-10-06**: David's wedding order (Asheville venue,
  David+Sarah, romantic, 1 photo) was un-rejected server-side (marker deleted,
  status→active) after the false "lets giddy up" kill — reloading /start and
  sending any message resumes it with all progress intact.
- **GitHub 2026-10-06**: local git repo initialized and committed (85 files,
  `941b778`; `hidden_files/mayfly.env` excluded via .gitignore; README added).
  Push to `dsing13/mayfly` BLOCKED: the API refuses creation ("name already
  exists on this account") while the repo 404s everywhere — likely a stale
  name reservation on GitHub's side. David to create the empty private repo
  himself, then Nova pushes.

## Theme widgets (interactive, 2026-10-06)
- Shared block `site/themes/_widgets.html` injected by `scripts/inject-widgets.py`
  (idempotent, version-stamped — v3 current). Edit the shared file, bump the
  version markers (`MAYFLY WIDGETS vN` CSS + `MAYFLY WIDGETS-JS vN` JS), re-run
  the injector. GOTCHA: the injector only refreshed CSS on version bumps, not
  JS — fixed 2026-10-06 (JS now versioned too; both refresh together).
- Widgets: photo lightbox, event countdown, add-to-calendar (.ics), directions,
  RSVP buttons, share button, details accordion, verdict buttons (play theme).
  New optional placeholders: {{event_iso}}, {{venue_text}}, {{rsvp_contact}},
  {{verdict_answer}} (verdict block hides when empty — the old hardcoded
  "She said yes. Obviously." was removed 2026-10-06).
- `{{hero_image}}` is NOT auto-filled from --images: set explicitly in vars.json
  to /_img/<sub>/photo-N.jpg (publisher prints the mapping).

## Permanent examples (LIVE 2026-10-06)
- 8 example sites, one per theme, at `<theme>.trymayfly.com`
  (celebrate/invite/announce/sell/remember/rally/inform/play). Built with
  build-site.py (`--ttl-days 366 --tier example`), content vars in
  `examples/vars-<theme>.json`, photos in `examples/photos/<theme>/`
  (4/theme: 1 hero + 3 gallery, Wikimedia Commons).
- Example vars enriched 2026-10-06 with event_iso/venue_text/rsvp_contact so
  the widget demos are live (countdowns tick; invite/play have accordions).
  NOTE: example event dates are fixed — when they pass, countdowns show
  "that was a good one"; refresh event_iso in vars + rebuild yearly-ish.
- **Pinned against the sweep**: `scripts/pin-examples.py` sets `pinned:true`
  on each `site:<sub>` record; the worker's `scheduled` handler skips
  pinned records (verified by simulation against the deployed code). The pin
  script also swaps the countdown badge for a static "permanent example ·
  made with Mayfly" badge (data-expires="" → badge JS returns early) and
  strips sections with empty galleries.
- Landing page has a "See what's possible" gallery (8 cards → the example
  subdomains); source `site/index.html`, live in KV `page:_landing`.

## Gotchas learned
- build-site.py now writes the API JSON body to a temp file and uses curl
  `--data-binary @file` (2026-10-06): passing it via `--data` as a CLI arg hit
  "Argument list too long" once images were base64'd into the payload.
- Theme `{{hero_image}}` is NOT auto-filled from --images: set it explicitly in
  vars.json to `/_img/<sub>/<filename>` (publisher prints the mapping, e.g.
  `hero.jpg -> /_img/pawty/photo-1.jpg`). Same for gallery_html figures.
- Resize customer photos before publishing (PIL thumbnail to ~1200px, q82):
  a 3.5MB phone photo becomes ~240KB — the publisher path can't take
  multi-MB payloads gracefully.
- This account's workers.dev doesn't serve the script (CF 1042) — test via a
  temporary zone route on an owned domain instead (added + removed
  mayfly-test.charlotteparkphotos.com; route+DNS deleted after test).
- KV is eventually consistent: reads right after a write can 404 for ~60s.
- Python urllib through the egress proxy is flaky vs Cloudflare edge; use curl
  for live-edge testing, and always send a browser User-Agent (zone bot
  protection 403s Python-urllib's UA).
- End-to-end verified 2026-09-26: health, publish, subdomain serve, metadata,
  delete, 404 page, exact TTL math (604800000ms = 7d).
