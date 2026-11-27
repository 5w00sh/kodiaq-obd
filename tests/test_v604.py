"""Test 11 (v6.0.4): real-tablet fixes.
 1. layout is sized from the VISIBLE viewport (visualViewport / dvh), incl. system-bar sizes 800x1100, 1280x700, 412x840, 360x690, 760x320
 2. after Stop / Demo / on load: live tiles are "–", trip average + cost + range stay but are labelled "last trip" / "last known"; demo values never persist
 3. the "Ignition on -> Connect" hint has its own row (never over a tile) and shows only while not connected
 4. hot coolant (> 105 C, clears <= 103) forces the coolant tile visible in every mode and viewport"""
import json, time
from common import app, check, OUT

VIEWPORTS = [(412, 915), (915, 412), (800, 1280), (1280, 800), (360, 760), (760, 360), (800, 1100), (1280, 700), (412, 840), (360, 690), (760, 320)]
def ls(page, key): return json.loads(page.evaluate(f"localStorage.getItem('kobd_{key}') || 'null'"))
def seed(page, **kv):
    page.context.add_init_script(f"for (const [k, v] of Object.entries({json.dumps(kv)})) localStorage.setItem('kobd_' + k, JSON.stringify(v));")
    page.reload(); page.wait_for_timeout(500)
def wait(page, expr, t=20000): page.wait_for_function(expr, timeout=t)
def connect(page):
    page.click("#btnConnect"); wait(page, "document.getElementById('status').textContent.includes('Connected')")
def txt(page, sel): return " ".join(page.inner_text(sel).split())
TRIPS = [{"date": f"2026-11-{i:02d}T08:00:00Z", "miles": 12.0, "litres": 1.2, "mpg": 45.5 - i*0.1, "per10": 1, "score": 80} for i in range(1, 6)]

FIT = """() => {   // no scroll, nothing off screen, no truncated labels, hint above the grid
  const bad = [], pane = document.getElementById('p_drive'), de = document.scrollingElement;
  const shown = el => !!el && getComputedStyle(el).display !== 'none' && el.getClientRects().length > 0;
  if (pane.scrollHeight > pane.clientHeight + 1) bad.push(`Drive pane scrolls (${pane.scrollHeight}>${pane.clientHeight})`);
  if (de.scrollHeight > innerHeight + 1 || de.scrollWidth > innerWidth + 1) bad.push('page scrolls');
  const nav = document.querySelector('nav').getBoundingClientRect(); if (nav.bottom > innerHeight + 1) bad.push('nav below the visible area');
  const dr = pane.querySelector('.drive').getBoundingClientRect(), hint = document.getElementById('emptyHint'), hr = hint.getBoundingClientRect();
  if (shown(hint)) { if (hr.bottom > dr.top + 1) bad.push('hint overlaps the tile grid'); if (hint.scrollWidth > hint.clientWidth + 1) bad.push('hint text cut'); }
  for (const t of pane.querySelectorAll('.tile')) { if (!shown(t)) continue; const r = t.getBoundingClientRect(), l = t.querySelector('.lab');
    if (r.bottom > innerHeight + 1 || r.right > innerWidth + 1 || r.top < hr.top - 1) bad.push(t.id + ' off screen');
    if (shown(l) && l.scrollWidth > l.clientWidth + 1) bad.push(t.id + ' label truncated: ' + l.textContent);
    if (shown(l) && parseFloat(getComputedStyle(l).fontSize) < 12) bad.push(t.id + ' label < 12px');
    if (hr.width && shown(hint) && r.top < hr.bottom - 1 && r.bottom > hr.top + 1 && r.left < hr.right && r.right > hr.left) bad.push('hint over ' + t.id); }
  const sp = document.querySelector('#t_speed .val'), cs = getComputedStyle(sp), c = document.createElement('canvas').getContext('2d'); c.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
  const m = c.measureText('0123456789'), ink = m.actualBoundingBoxAscent + m.actualBoundingBoxDescent, need = Math.min(innerWidth, innerHeight) < 700 ? 72 : 96;
  if (ink < need) bad.push(`speed digits ${ink.toFixed(0)}px < ${need}`);
  return bad;
}"""

# ---------- 1. visible viewport ----------
with app(viewport=(800, 1280), mock=False) as page:
    page.context.add_init_script("Object.defineProperty(window.visualViewport, 'height', {get: () => window.innerHeight - 180, configurable: true});")   # system bars eat 180 px that innerHeight still counts
    page.reload(); page.wait_for_timeout(600)
    h = page.evaluate("innerHeight") - 180
    nb = page.evaluate("document.querySelector('nav').getBoundingClientRect().bottom"); bh = page.evaluate("document.body.getBoundingClientRect().height")
    check(abs(nb - h) <= 1 and abs(bh - h) <= 1, f"layout follows visualViewport: nav bottom {nb:.0f}, body {bh:.0f}, visible {h}")
    page.click("#btnDemo"); page.wait_for_timeout(1500)
    check(page.evaluate("document.getElementById('t_oil')").__class__ is not None and not page.evaluate(FIT), "800 x (1280-180) Drive tab fits: " + "; ".join(page.evaluate(FIT)))
    check(not page.is_visible("#t_oil"), "...and the lowest-priority tile (Oil) is dropped instead of being cut off")
    page.screenshot(path=str(OUT / "v604-visual-viewport-800x1100.png"))
    page.evaluate("ds = 13; window.__forceFill = true"); page.wait_for_timeout(600)
    check(not page.evaluate(FIT), "with regen banner + fill card as well: " + "; ".join(page.evaluate(FIT)))

for theme in ("night", "day"):
    for w, h in VIEWPORTS:
        with app(viewport=(w, h), mock=False, theme=theme) as page:
            # ---------- 3. hint + 2. idle on load ----------
            seed(page, trips=TRIPS, fuelLast={"pct": 62, "t": int(time.time()*1000) - 7200000})
            check(page.is_visible("#emptyHint") and "Ignition on" in page.inner_text("#emptyHint"), f"{theme} {w}x{h} hint shown when not connected")
            bad = page.evaluate(FIT); check(not bad, f"{theme} {w}x{h} idle: fits, hint has its own row, no overlap" + ("" if not bad else ": " + "; ".join(bad)))
            if theme == "night": page.screenshot(path=str(OUT / f"v604-idle-{w}x{h}.png"))
            check(all(txt(page, f"#t_{n} .val").startswith("–") for n in ("speed", "rpm", "mpgInst", "lph", "coolant", "oil")), f"{theme} {w}x{h} on load: live tiles are –")
            check(page.is_visible("#t_range") and "last known" in txt(page, "#t_range .lab").lower() and page.inner_text("#t_range .num").isdigit(), f"{theme} {w}x{h} range kept, labelled: {txt(page, '#t_range .lab')} / {txt(page, '#t_range .val')}")
            check("last trip" in txt(page, "#t_mpgTrip .lab").lower() and txt(page, "#t_mpgTrip .val").startswith("45.0"), f"{theme} {w}x{h} trip average kept, labelled: {txt(page, '#t_mpgTrip .lab')} {txt(page, '#t_mpgTrip .val')}")
            page.click("#btnBig"); page.wait_for_timeout(500)
            bad = page.evaluate(FIT); check(not bad, f"{theme} {w}x{h} idle + Big mode: fits" + ("" if not bad else ": " + "; ".join(bad)))
            if theme == "night": page.screenshot(path=str(OUT / f"v604-idle-big-{w}x{h}.png"))
            page.click("#btnBig")
            # ---------- demo -> stop ----------
            page.click("#btnDemo"); page.wait_for_timeout(2500)
            check(not page.is_visible("#emptyHint"), f"{theme} {w}x{h} hint hidden while connected (Demo)")
            check(txt(page, "#t_speed .val")[0].isdigit(), f"{theme} {w}x{h} demo shows live speed")
            ntrips = len(ls(page, "trips"))
            page.click("#btnStop"); page.wait_for_timeout(500)
            check(page.is_visible("#emptyHint"), f"{theme} {w}x{h} hint is back after Stop")
            vals = {n: txt(page, f"#t_{n} .val") for n in ("speed", "rpm", "mpgInst", "lph", "coolant", "oil", "score")}
            check(all(v.startswith("–") for v in vals.values()), f"{theme} {w}x{h} after Demo stops: live tiles –  {vals}")
            check(txt(page, "#t_mpgTrip .val").startswith("45.0") and "last trip" in txt(page, "#t_mpgTrip .lab").lower(), f"{theme} {w}x{h} after Demo: trip average is the saved trip's, not the demo's: {txt(page, '#t_mpgTrip .val')}")
            check(txt(page, "#t_cost .val").startswith("£1.74") or not page.is_visible("#t_cost"), f"{theme} {w}x{h} after Demo: trip cost is the saved trip's: {txt(page, '#t_cost .val')}")
            check(txt(page, "#t_range .num") == str(round(62*58/100/0.1)) and "last known" in txt(page, "#t_range .lab").lower(), f"{theme} {w}x{h} after Demo: range from the last real level: {txt(page, '#t_range .val')}")
            check(len(ls(page, "trips")) == ntrips, f"{theme} {w}x{h} demo saved no trip")
            bad = page.evaluate(FIT); check(not bad, f"{theme} {w}x{h} after Stop: fits" + ("" if not bad else ": " + "; ".join(bad)))
            check(not page.errors, f"{theme} {w}x{h} no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))

# ---------- demo with NO history: nothing at all may be left over ----------
with app(viewport=(412, 915), mock=False) as page:
    page.click("#btnDemo"); page.wait_for_timeout(3000); page.click("#btnStop"); page.wait_for_timeout(500)
    vals = {n: txt(page, f"#t_{n} .val") for n in ("speed", "rpm", "mpgInst", "lph", "coolant", "oil", "score", "mpgTrip", "cost")}
    check(all(v.startswith("–") for v in vals.values()), f"no history + Demo stopped: everything –  {vals}")
    check(txt(page, "#t_range .num") == "–" and "last known" not in txt(page, "#t_range .lab").lower() and "last trip" not in txt(page, "#t_mpgTrip .lab").lower(), "no history: no 'last known' / 'last trip' labels on empty tiles")
    page.screenshot(path=str(OUT / "v604-after-demo-empty.png"))

# ---------- real (mock) connection, then Stop ----------
with app(viewport=(412, 915)) as page:
    seed(page, trips=TRIPS, fuelLast={"pct": 62, "t": int(time.time()*1000) - 600000})
    page.evaluate("FUEL_WIN_MS = 4000; __mock.fuelPct = 50; __mock.cruise = 50"); connect(page); page.wait_for_timeout(9000)
    check(txt(page, "#t_speed .val")[0].isdigit() and "last known" not in txt(page, "#t_range .lab").lower(), f"connected: live speed {txt(page, '#t_speed .val')}, no 'last known' on Range ({txt(page, '#t_range .val')})")
    page.click("#btnStop"); page.wait_for_timeout(600)
    vals = {n: txt(page, f"#t_{n} .val") for n in ("speed", "rpm", "mpgInst", "lph", "coolant", "oil")}
    check(all(v.startswith("–") for v in vals.values()), f"after Stop (real connection): live tiles –  {vals}")
    check("last known" in txt(page, "#t_range .lab").lower() and "last known" in txt(page, "#t_remain .lab").lower() and page.inner_text("#t_range .num").isdigit(), f"range kept: {txt(page, '#t_range .lab')} {txt(page, '#t_range .val')}")
    page.screenshot(path=str(OUT / "v604-after-stop.png"))
    check(not page.errors, "no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))

# ---------- 4. hot coolant: > 105 on, <= 103 off, visible in EVERY mode/viewport ----------
for w, h in ((360, 690), (760, 320), (412, 915), (800, 1100), (1280, 700), (915, 412)):
    for big in (False, True):
        with app(viewport=(w, h)) as page:
            seed(page, trips=TRIPS, big=big)
            page.evaluate("FUEL_WIN_MS = 3000; __mock.fuelPct = 60"); connect(page); page.wait_for_timeout(5000)
            def st(c):
                page.evaluate(f"__mock.coolantC = {c}"); page.wait_for_timeout(2600)
                return page.evaluate("document.getElementById('p_drive').classList.contains('hotc')"), page.is_visible("#t_coolant")
            tag = f"{w}x{h} {'Big' if big else 'normal'}"
            on = st(106); check(on == (True, True), f"{tag}: 106 C -> hot, coolant tile visible {on}")
            if on[1]:
                bad = page.evaluate(FIT); check(not bad, f"{tag}: hot coolant, layout still fits" + ("" if not bad else ": " + "; ".join(bad)))
                check(page.inner_text("#t_coolant .val").split()[0] == "106" and "hot" in page.evaluate("document.getElementById('t_coolant').className"), f"{tag}: shown as 106, amber")
            if (w, h) in ((360, 690), (760, 320)): page.screenshot(path=str(OUT / f"v604-hot-{w}x{h}{'-big' if big else ''}.png"))
            check(st(104)[0] and page.is_visible("#t_coolant"), f"{tag}: 104 C stays (hysteresis)")
            off = st(103); check(off[0] is False, f"{tag}: 103 C clears")
            if (w, h) in ((360, 690), (760, 320)): check(off[1] is False, f"{tag}: tile goes away again where the tiers hide it")
            check(not page.errors, f"{tag} no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))
