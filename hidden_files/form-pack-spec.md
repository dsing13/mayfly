# Mayfly build spec — form intake + freemium + Plus pack + Rush (David-approved 2026-10-27)

Work in ~/workspace/mayfly. Run `npm test` at the end; all tests must pass.
Do NOT deploy. Do NOT touch hidden_files/mayfly.env. Do NOT commit.

## Decisions (locked by David)
- Chat intake is replaced by a Typeform-style progressive form at /start.
- Freemium: first 5 published sites free (any duration), then 1 free site per
  calendar month. Paid base price (existing TIERS) applies only beyond that.
- Plus pack: $5 per site, sold at the end of the form ("Make it work harder").
- Rush: $3 per site — front of the build line, live in ~10 minutes.
  Standard delivery promise is 2 hours.
- AI is used ONLY for moderation now, never for conversation.

## 1. worker/mayfly-router.js

Keep ALL existing endpoints working (chat endpoints stay live but unused by the
new UI — do not delete them). Keep REQUIRED, TIERS, finalizeOrder/order storage
shapes, the admin orders API, and uploads as they are except where noted.

### Freemium credits
- KV key `credits:<sha256 hex of lowercased trimmed email>` →
  JSON {starterUsed: int, monthlyUsed: "YYYY-MM" | null}.
- Pure helper `creditFor(record, nowDate)` → {kind: 'starter'|'monthly'|null,
  starterLeft: int, monthlyAvailable: bool}: starter while starterUsed < 5;
  else monthly while monthlyUsed !== current "YYYY-MM" (UTC); else null.
  Export it via _test.
- `POST /api/intake/eligibility` {email} → {ok:true, free, kind, starterLeft,
  monthlyAvailable}. Read-only (no KV write).

### Submit endpoint
`POST /api/intake/submit` {sessionId, theme, fields:{}, details, tone, tier,
email, photos: "uploaded"|"none", pack: bool, rush: bool}
- Load the intake session by sessionId (create an empty one if missing so the
  form can upload photos before ever chatting). Uploads list comes from the
  session record, exactly as the chat flow does.
- Build an order object and run the EXISTING checkOrderComplete() against it
  (with details synthesized from the fields if the user left details short:
  join field values into a sentence; the form always sends a details field).
  If incomplete → 400 {error:'incomplete', missing:[...]}.
- If uploads.length > 6 and pack is false → 400
  {error:'pack_required_for_photos', message:'More than 6 photos needs the Plus pack.'}
- Moderation: run the EXISTING moderateText() ONCE over the concatenated text
  (theme + all field values + details + tone). 'reject' → markRejected +
  {ok:false, rejected:true, message: REJECT_LINE}. Any thrown AI error →
  proceed anyway with moderation:'unreviewed'. 'unclear' → proceed with
  moderation:'unclear'. Otherwise moderation:'ok'. NEVER fail the submit for
  an AI infrastructure error.
- Money: basePrice = credit ? 0 : TIERS[tier].price. extras = (pack?5:0) +
  (rush?3:0). amountDue = basePrice + extras.
- Payment links (array in the response, and stored on the order):
  - basePrice > 0 → {label: TIERS[tier].label, url: TIERS[tier].link +
    '?client_reference_id=' + sessionId}
  - extras > 0 → use EXTRA_LINKS (new constant near TIERS, keys pack/rush/both,
    string values, MAY BE EMPTY STRINGS for now — Nova fills them pre-deploy;
    skip any whose value is empty) with the same client_reference_id suffix.
- Consume the credit (starterUsed++ or monthlyUsed = current month) and write
  the credits record ONLY on a successful order.
- Finalize the order by reusing the existing finalizeOrder() path (keepUploads
  etc.), then PATCH-equivalent update the stored record with these extra
  fields: pack, rush, creditKind, amountDue, paymentLinks, moderation,
  delivery: rush ? 'rush-10min' : 'standard-2h'. If an order already exists
  for this sessionId, return it instead of double-creating/double-charging a
  credit.
- Response: {ok:true, orderId, free: (basePrice===0), creditKind, amountDue,
  paymentLinks, delivery}.

### Uploads
- Raise MAX_UPLOADS from 6 to 12. Vision moderation per upload unchanged.
  Update any user-facing copy in responses that says 6.

### Tests
Add tests (reuse test/fakes.mjs patterns; mock env.AI.run so moderation
returns OK): creditFor starter/monthly/paid boundaries; submit happy path
(free starter credit consumed, amountDue 0, no payment links); submit with
pack+rush on a free credit → amountDue 8 with extras link present when
EXTRA_LINKS.both is set in the test env/constant stub; submit with >6 photos
and no pack → 400; submit when moderation AI throws → order still created with
moderation 'unreviewed'. Update existing tests if MAX_UPLOADS copy breaks them.
All tests green at the end.

## 2. site/start.html — full rewrite as a progressive form

Same visual system as the current page (CSS variables, serif brand, paper
background, mobile-first, max-width ~680px). NO chat bubbles, NO textarea
composer. Vanilla JS, no libraries.

Flow (one question per screen, progress bar "Step n of m", Back link,
Enter advances, per-step validation with inline error text):
1. Theme: 8 tappable cards (celebrate, invite, announce, sell, remember,
   rally, inform, play) with plain human names + one-line descriptions.
2. That theme's REQUIRED fields, one screen each, using the worker REQUIRED
   map keys. Friendly labels/questions per key (reuse the spirit of
   MISSING_QUESTIONS in the worker). datetime/date/when fields use
   datetime-local or date inputs as appropriate; the stored value is a
   human-readable string.
3. Details: textarea "Anything else the page should say?" (optional, but the
   form supplies it to the worker as details).
4. Photos: file input with the EXISTING shrink-to-2000px / EXIF-strip /
   base64 upload code from the current start.html, posting to
   /api/intake/upload with the sessionId. Up to 12; caption notes the first 6
   are included free, 12 with the Plus pack. A "No photos" continue path sets
   photos:'none'.
5. Tone: chips (Warm & friendly, Playful, Elegant, Simple & direct, Somber)
   + optional free-text.
6. Email: validated with the same regex the worker uses. On advancing, POST
   /api/intake/eligibility and remember the result.
7. Duration: the 5 tiers as cards. If eligibility says free, every card shows
   "Free" plus a line naming the credit ("Starter page — free", "This month's
   free page"). Otherwise cards show the current prices.
8. Add-ons: two toggle cards —
   - Plus pack, $5: theme-flavored first item (celebrate/invite/play/rally/
     inform: "Printable QR poster"; sell: "Printable QR yard sign";
     remember: "Printable QR card for the service"; announce: "Printable QR
     announcement card") then for all: "No Mayfly badge on your page",
     "Up to 12 photos", "One free round of edits", "Priority help".
   - Rush, $3: "Front of the line — your page is live in about 10 minutes."
     Note the standard: "Standard build: link by email within 2 hours."
9. Review: summary of everything + total due (base + pack + rush, showing
   Free where a credit applies). Submit button.
10. Done screen: if amountDue > 0, render each payment link as a "Pay $X"
    button (new tab) and explain the page is built once payment lands;
    if free, say it's in the build queue. Always state the delivery promise
    (about 10 minutes for rush, within 2 hours standard) and that the link
    arrives at their email. "Make another page" resets.

Draft persistence: save form state to localStorage (key mayfly_form_v1) on
every step; restore on load. Session id: keep using localStorage mayfly_sid
(create if absent) so uploads and submit share it.
Update the <title>/meta: no mention of chat ("Answer a few quick questions…").

## 3. scripts/build-site.py — pack deliverables
- New --no-badge flag: removes the "made with Mayfly" footer badge from the
  built HTML. Find the badge markup in the themes and remove it robustly
  (anchor on its actual class/id); unreplaced-placeholder safety net stays.
- New --poster flag: after building, generate a print poster PNG
  (1748×2480, A4 @150dpi) with PIL: paper-white background, site title big,
  one line of when/where from vars when present, a large QR code pointing at
  the site URL, and the URL in text under it. QR via the `segno` package —
  add segno to requirements.txt; if segno is unavailable at runtime, warn
  and skip the poster WITHOUT failing the build. Write poster next to the
  output as <sub>-poster.png (for --out local builds) and print its path.
- Both flags are no-ops for themes/builds that don't use them; existing
  behavior and CLI unchanged otherwise.

## 4. site/index.html — copy only (structure/classes unchanged)
- Hero facts line: "First 5 pages free · then one free every month · No account"
- Any "chat"/conversation wording in How-it-works → form wording
  ("Answer a few quick questions").
- Delivery promise where mentioned: built and emailed within about 2 hours;
  the #thanks banner says the same.
- Pricing section: keep the tier rows (they're the extra-page prices), add a
  short line/block covering: first 5 pages free + one free monthly, the $5
  Plus pack (QR poster, no badge, 12 photos, an edit round), and $3 Rush
  (live in ~10 minutes instead of ~2 hours).

## Constraints
- Copy: human, plain, no AI mentions, no "real human" claims, no emoji in UI.
- Never invent a URL: EXTRA_LINKS start empty and are skipped when empty.
- Existing orders/admin/deploy flow must keep working; deploy script already
  uploads site/start.html and the worker — no deploy changes needed.
