#!/usr/bin/env python3
"""Render fresh mobile demo screenshots for all 8 Mayfly themes.

Fills each theme template with realistic sample content (no eyebrows, no
faux QR), writes demos/<theme>.html, then screenshots at 390px wide with
headless Chromium into demos/<theme>.png.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, "/tmp")
from cdp_shot import screenshot as cdp_screenshot

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
THEMES_DIR = os.path.join(ROOT, "site", "themes")
DEMOS_DIR = os.path.join(ROOT, "demos")
CHROME = "/opt/meta-chromium/chrome"
WIDTH = 390
EXPIRY = "2026-10-05T12:00:00+00:00"

FIG = ('<figure><img src="img/{t}.jpg" alt="" loading="lazy">'
       '<figcaption>{cap}</figcaption></figure>')

SAMPLES = {
    "celebrate": {
        "title": "Maya Turns <em>Thirty</em>",
        "subtitle": "A backyard birthday — cake, string lights, and the people she likes most. Come hungry.",
        "cta_html": '<a class="btn-glow" href="sms:+17045550134">Text Maya you\u2019re in \U0001f389</a>'
                    '<a class="btn-ghost" href="#details">The details</a>',
        "details_html":
            '<div class="kv-row"><span>When</span><span>Saturday, June 14 \u00b7 4:00 PM till late</span></div>'
            '<div class="kv-row"><span>Where</span><span>Maya\u2019s backyard, 412 Elmwood Ave, Charlotte</span></div>'
            '<div class="kv-row"><span>Bring</span><span>Just yourself \u2014 food and drinks are covered</span></div>'
            '<div class="kv-row"><span>Theme</span><span>Golden hour casual. Dress for photos.</span></div>'
            '<div class="kv-row"><span>Kids</span><span>Very welcome \u2014 there\u2019ll be a kiddie pool</span></div>',
        "gallery_html": (FIG.format(t="celebrate", cap="Maya, age 7, already the boss")
                         + FIG.format(t="celebrate", cap="Last year\u2019s infamous pi\u00f1ata")),
        "contact_html": '<h2>Can you make it?</h2><p>Text Maya at '
                        '<a href="tel:+17045550134">(704) 555-0134</a><br>or email '
                        '<a href="mailto:maya@example.com">maya@example.com</a></p>',
    },
    "invite": {
        "title": "June <em>&</em> Theo",
        "subtitle": "request the honour of your presence \u2014 Saturday, October 18th",
        "cta_html": '<a class="btn-glow" href="mailto:juneandtheo@example.com">RSVP</a>'
                    '<a class="btn-ghost" href="#schedule">Order of events</a>',
        "details_html":
            '<div class="slot"><span class="time">3:30 PM</span><span class="what">Ceremony<small>under the oak grove \u2014 unplugged, please</small></span></div>'
            '<div class="slot"><span class="time">4:30 PM</span><span class="what">Cocktail hour<small>on the terrace, string quartet</small></span></div>'
            '<div class="slot"><span class="time">6:00 PM</span><span class="what">Dinner & toasts<small>in the barn \u2014 seating chart at the door</small></span></div>'
            '<div class="slot"><span class="time">8:00 PM</span><span class="what">Dancing<small>until the lights (politely) come on</small></span></div>',
        "details2_html":
            '<div class="kv-row"><span>Venue</span><span>The Bradford Barn, 88 Orchard Ln, Huntersville</span></div>'
            '<div class="kv-row"><span>Parking</span><span>Field lot past the barn \u2014 shuttle from 3:00 PM</span></div>'
            '<div class="kv-row"><span>Dress</span><span>Garden formal. Grass-friendly shoes advised.</span></div>'
            '<div class="kv-row"><span>Plus-ones</span><span>Named on your invitation \u2014 ask us if unsure</span></div>',
        "gallery_html": (FIG.format(t="invite", cap="Asheville, 2022 \u2014 the first trip")
                         + FIG.format(t="invite", cap="The venue at golden hour")),
        "contact_html": '<h2>Questions? Stuck on the seating chart?</h2><p>Email '
                        '<a href="mailto:juneandtheo@example.com">juneandtheo@example.com</a></p>',
    },
    "announce": {
        "title": "Welcome, <em>Baby Noor</em>",
        "subtitle": "born September 21st, already running the household",
        "cta_html": '<a class="btn-glow" href="mailto:layla@example.com">Send love</a>'
                    '<a class="btn-ghost" href="#photos">See photos</a>',
        "details_html":
            '<div class="stat"><div class="v">7 lb 4 oz</div><div class="l">Weight</div></div>'
            '<div class="stat"><div class="v">19 in</div><div class="l">Length</div></div>'
            '<div class="stat"><div class="v">2:14 AM</div><div class="l">Arrival</div></div>',
        "details2_html":
            '<div class="kv-row"><span>Parents</span><span>Layla & Omar Haddad</span></div>'
            '<div class="kv-row"><span>Big brother</span><span>Adam, age 3 \u2014 taking it well, mostly</span></div>'
            '<div class="kv-row"><span>Visits</span><span>After Oct 5, please \u2014 text Layla first</span></div>'
            '<div class="kv-row"><span>Meal train</span><span>Link below \u2014 the lasagna era is over, try soup</span></div>',
        "note_html": '<p>She has Omar\u2019s eyes and Layla\u2019s opinions. We\u2019re so tired and so happy. \u2014 Grandma Salma</p>',
        "gallery_html": (FIG.format(t="announce", cap="Hour one")
                         + FIG.format(t="announce", cap="Meeting Adam")),
        "contact_html": '<h2>Say hello (quietly)</h2><p>Meal train & visit sign-up: '
                        '<a href="mailto:layla@example.com">layla@example.com</a></p>',
    },
    "sell": {
        "title": "Maple Street <em>Yard Sale</em>",
        "subtitle": "Two households, one driveway, an unreasonable amount of stuff. Everything priced to move \u2014 Saturday only.",
        "cta_html": '<a class="btn-glow" href="sms:+17045550198">Text about an item</a>'
                    '<a class="btn-ghost" href="#details">When & where</a>',
        "details_html":
            '<div class="kv-row"><span>When</span><span>Saturday only \u00b7 8:00 AM \u2013 2:00 PM</span></div>'
            '<div class="kv-row"><span>Where</span><span>1214 & 1216 Maple St, Charlotte \u2014 look for the balloons</span></div>'
            '<div class="kv-row"><span>Payment</span><span>Cash, Venmo, or Zelle. No holds.</span></div>'
            '<div class="kv-row"><span>Fine print</span><span>Everything sold as-is. Early birds welcome at 7:45.</span></div>',
        "items_html":
            '<div class="item"><div class="thumb i1"></div><div><h3>Mid-century dresser</h3><p>Solid wood, great shape, drawers glide</p></div><span class="p">$85</span></div>'
            '<div class="item"><div class="thumb i2"></div><div><h3>Kids\u2019 bikes (2)</h3><p>16" and 20", helmets included</p></div><span class="p">$40</span></div>'
            '<div class="item"><div class="thumb i3"></div><div><h3>KitchenAid mixer</h3><p>Barely used, all attachments</p></div><span class="p">$120</span></div>'
            '<div class="item"><div class="thumb i4"></div><div><h3>Box of vinyl LPs</h3><p>~60 records, mostly 70s rock</p></div><span class="p">$50</span></div>',
        "gallery_html": (FIG.format(t="sell", cap="The driveway, half-unloaded")
                         + FIG.format(t="sell", cap="Free box \u2014 yes, really")),
        "contact_html": '<h2>Want something held? <em>Too bad.</em></h2><p>First come, first served \u2014 but text '
                        '<a href="tel:+17045550198">(704) 555-0198</a> with questions.</p>',
    },
    "remember": {
        "title": "Robert <em>\u201cBob\u201d</em> Hale",
        "subtitle": "1948 \u2013 2026 \u00b7 Husband, father, and the world\u2019s worst fisherman",
        "cta_html": '<a class="btn-ghost" href="mailto:carol@example.com">Share a memory</a>',
        "tribute_html":
            '<p>Bob believed a bad day fishing beat a good day anywhere else, and he lived like it. He is survived by his wife of 51 years, Carol, their three kids, and seven grandkids who all know exactly how he liked his coffee.</p>'
            '<p>He never met a stranger at the lake, never let a grandkid lose at checkers on purpose, and never \u2014 not once \u2014 caught the big one he spent forty years talking about.</p>',
        "details_html":
            '<div class="kv-row"><span>Service</span><span>Saturday, October 4 \u00b7 11:00 AM</span></div>'
            '<div class="kv-row"><span>Where</span><span>St. John\u2019s Chapel, 200 Hawthorne Ln</span></div>'
            '<div class="kv-row"><span>Reception</span><span>To follow at the fellowship hall</span></div>',
        "gallery_html": (FIG.format(t="remember", cap="Lake James, 2019")
                         + FIG.format(t="remember", cap="Fifty years, same grin")),
        "contact_html": '<h2>Share a memory</h2><p>In lieu of flowers, the family asks for your favorite Bob story: '
                        '<a href="mailto:carol@example.com">carol@example.com</a></p>',
    },
    "rally": {
        "title": "Sandlot <em>Sluggers</em>",
        "subtitle": '8\u20132 and climbing. Next game: Saturday, 10 AM, Field 3. <span class="hl">Bring the noise.</span>',
        "cta_html": '<a class="btn-glow" href="sms:+17045550177">Join the squad</a>'
                    '<a class="btn-ghost" href="#details">Team info</a>',
        "details_html":
            '<div class="row head"><span class="rk">#</span><span class="tm">Team</span><span class="rc">W\u2013L</span></div>'
            '<div class="row us"><span class="rk">1</span><span class="tm">Sandlot Sluggers \u2605</span><span class="rc">8\u20132</span></div>'
            '<div class="row"><span class="rk">2</span><span class="tm">The Curveballs</span><span class="rc">7\u20133</span></div>'
            '<div class="row"><span class="rk">3</span><span class="tm">Pineville Pythons</span><span class="rc">6\u20134</span></div>'
            '<div class="row"><span class="rk">4</span><span class="tm">Dilworth Dingers</span><span class="rc">4\u20136</span></div>'
            '<div class="row"><span class="rk">5</span><span class="tm">South End Strikers</span><span class="rc">2\u20138</span></div>',
        "details2_html":
            '<div class="kv-row"><span>Next game</span><span>Sat Oct 3 \u00b7 10:00 AM \u00b7 Field 3 vs. Curveballs</span></div>'
            '<div class="kv-row"><span>Practice</span><span>Wednesdays 6 PM, same field</span></div>'
            '<div class="kv-row"><span>Dues</span><span>$25 for the season \u2014 Venmo @sluggers-mgr</span></div>'
            '<div class="kv-row"><span>Post-game</span><span>Birdsong Brewing, as is tradition</span></div>',
        "gallery_html": (FIG.format(t="rally", cap="Opening day walk-off")
                         + FIG.format(t="rally", cap="The trophy (aspirational)")),
        "contact_html": '<h2>Want to sub <em>this Saturday?</em></h2><p>Text Coach Ray at '
                        '<a href="tel:+17045550177">(704) 555-0177</a> \u2014 we always need an outfielder.</p>',
    },
    "inform": {
        "title": "Babysitter <em>Cheat Sheet</em>",
        "subtitle": "The Alvarez family \u2014 everything you need for Saturday night. Kids are angels. Mostly.",
        "cta_html": '<a class="btn-glow" href="sms:+17045550142">Text the parents</a>'
                    '<a class="btn-ghost" href="javascript:window.print()">Print this page</a>',
        "details_html":
            '<li><span class="box"></span><span>Wi-Fi: <strong>AlvarezHome_5G</strong> \u00b7 password <strong>sunnyporch42</strong><small>Yes, really. We know.</small></span></li>'
            '<li><span class="box"></span><span>Dinner at 6:00 \u2014 nuggets in the freezer, veggies already cut<small>Mateo (6) will claim he\u2019s not hungry. He is.</small></span></li>'
            '<li><span class="box"></span><span>Bath at 7:00, teeth, then one (1) episode<small>Bluey only. Do not negotiate on this.</small></span></li>'
            '<li><span class="box"></span><span>Bedtime 8:00 sharp \u2014 Sofia (3) sleeps with the hallway light on<small>Nightlight is in the top dresser drawer.</small></span></li>'
            '<li><span class="box"></span><span>Snacks are fine, candy is not (we\u2019ll know)<small>Popcorn in the pantry, top shelf.</small></span></li>'
            '<li><span class="box"></span><span>Back door sticks \u2014 lift AND pull<small>Front door deadbolt works normally.</small></span></li>',
        "emergency_html":
            '<h3>\U0001f6a8 Just in case</h3><p>Parents: <a href="tel:+17045550142">Elena (704) 555-0142</a> \u00b7 '
            '<a href="tel:+17045550143">Marco (704) 555-0143</a><br>Neighbor Rosa (nurse, two doors down): '
            '<a href="tel:+17045550144">(704) 555-0144</a><br>Pediatrician after-hours: '
            '<a href="tel:+17045550100">(704) 555-0100</a> \u00b7 Poison control: '
            '<a href="tel:+18002221222">1-800-222-1222</a></p>',
        "gallery_html": "",
        "contact_html": '<h2>We\u2019re at dinner, not in another time zone</h2><p>Text anytime \u2014 we keep phones on vibrate.<br>'
                        '<a href="tel:+17045550142">(704) 555-0142</a></p>',
    },
    "play": {
        "title": "Priya, will you go to <em>prom</em> with me?",
        "subtitle": 'Yes, this is a whole website. Yes, it was worth it. \u2014 <span class="sig">Dev</span>',
        "cta_html": '<a class="btn-glow" href="sms:+17045550155">Text Dev your answer</a>'
                    '<a class="btn-ghost" href="#pitch">Read the pitch</a>',
        "details_html":
            '<p class="big">Hear me out.</p>'
            '<p>You said you\u2019d only go with someone who \u2018makes an effort.\u2019 Well: domain registration, custom design, mobile-responsive layout. This is maximum effort.</p>'
            '<p>Also I already asked your group chat and they said yes on your behalf, but I wanted to do this properly.</p>'
            '<p>Prom is May 16th. I have the corsage situation handled. All that\u2019s missing is you.</p>',
        "gallery_html": (FIG.format(t="play", cap="Us, junior year, iconic")
                         + FIG.format(t="play", cap="The corsage shortlist")),
        "contact_html": '<h2>Respond at your earliest convenience</h2><p>Text Dev at '
                        '<a href="tel:+17045550155">(704) 555-0155</a></p>',
    },
}

THEMES = list(SAMPLES.keys())


def build(theme):
    with open(os.path.join(THEMES_DIR, theme + ".html")) as f:
        html = f.read()
    s = SAMPLES[theme]
    varmap = dict(s)
    varmap.setdefault("hero_image", "img/%s.jpg" % theme)
    varmap.setdefault("qr_svg", "")
    varmap["expires_at_iso"] = EXPIRY
    for k, v in varmap.items():
        html = html.replace("{{" + k + "}}", str(v))
    html = re.sub(r"\{\{[a-z0-9_]+\}\}", "", html)
    # sample <title> from the filled h1
    m = re.search(r"<h1 class=\"hero-title\">(.*?)</h1>", html, re.S)
    if m:
        plain = re.sub(r"<.*?>", "", m.group(1))
        html = re.sub(r"<title>.*?</title>", "<title>" + plain + "</title>",
                      html, count=1, flags=re.S)
    out = os.path.join(DEMOS_DIR, theme + ".html")
    with open(out, "w") as f:
        f.write(html)
    return out


def shot(path, out):
    # Full-page screenshot at 390 CSS px, 2x DPR, via CDP.
    cdp_screenshot("file://" + path, out, width=WIDTH, dpr=2)


def main():
    for theme in THEMES:
        path = build(theme)
        shot(path, os.path.join(DEMOS_DIR, theme + ".png"))


if __name__ == "__main__":
    main()
