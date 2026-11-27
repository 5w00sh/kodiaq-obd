"""Test 17 (v6.1.4): over-limit highlight on the Speed tile. Amber above the OSM limit, red above limit + tolerance (2 s to turn on, clears >= 1 mph under),
steady (no animation), only with a known limit + good GPS (<= 20 m). Tolerance setting: +2 mph / 10% + 2 mph / exact. Readability floors with the highlight on
are in test_readability.py (states 'over limit (red/amber)', and red carried through banner/Big states)."""
import json
from common import app, check, OUT, overpass_fixture, WEATHER

def wait(page, expr, t=20000): page.wait_for_function(expr, timeout=t)
def connect(page):
    page.click("#btnConnect"); wait(page, "document.getElementById('status').textContent.includes('Connected')")
def cls(page): return page.evaluate("[document.getElementById('t_speed').classList.contains('ovr'), document.getElementById('t_speed').classList.contains('ovw')]")

# ---------- the state machine ----------
with app(mock=False) as page:
    def run(seq, lim, mode):         # seq = [(ms, mph)] -> list of states
        return page.evaluate("([seq, lim, mode]) => { let st = {state:'', since:null}; return seq.map(([t, v]) => (st = overStep(st, v, lim, mode, t)).state); }", [seq, lim, mode])
    check(run([(0, 29), (100, 30), (200, 30.5), (300, 31.9), (400, 32)], 30, "p2") == ["", "", "amber", "amber", "amber"], "+2 mph: nothing at/below the limit, amber between limit and limit+2, still amber AT limit+2")
    check(run([(0, 32.5), (1900, 32.5), (2000, 32.5), (2100, 40)], 30, "p2") == ["amber", "amber", "over", "over"], "+2 mph: red only after 2.0 s continuously above limit+2 (amber meanwhile)")
    check(run([(0, 33), (1000, 31), (1500, 33), (3400, 33), (3500, 33)], 30, "p2") == ["amber", "amber", "amber", "amber", "over"], "dropping back resets the 2 s timer (a brief spike never turns red)")
    check(run([(0, 34), (2000, 34), (2100, 32.5), (2200, 32.1), (2300, 31.0), (2400, 31.5)], 30, "p2") == ["amber", "over", "over", "over", "amber", "amber"], "hysteresis: red holds until 1 mph under limit+tol (31.0), then amber")
    check(run([(0, 34), (2000, 34), (2100, 28.9), (2200, 29.5), (2300, 28.9)], 30, "p2") == ["amber", "over", "", "", ""] or run([(0, 34), (2000, 34), (2100, 28.9)], 30, "p2")[2] == "", "falling well below the limit clears everything")
    check(run([(0, 31), (100, 29.5), (200, 29.1), (300, 28.9)], 30, "p2") == ["amber", "amber", "amber", ""], "amber also has 1 mph hysteresis (no flicker around the limit)")
    check(run([(0, 56.9), (100, 57.1), (2100, 57.1), (2200, 55)], 50, "pct") == ["amber", "amber", "over", "amber"], "10% + 2 mph at 50: red line is 57 (55 is >1 mph under it: back to amber)")
    check(run([(0, 34.9), (100, 35.1), (2200, 35.1)], 30, "pct") == ["amber", "amber", "over"], "10% + 2 mph at 30: red line is 35")
    check(run([(0, 30), (100, 30.1), (2200, 30.1), (2300, 28.9)], 30, "exact") == ["", "amber", "over", ""], "exact: any speed over the limit, 2 s to red, clears 1 mph under")
    # setting
    page.evaluate("localStorage.removeItem('kobd_overTol'); tolUi()")
    page.click('nav button[data-p="car"]')
    check("+2 mph" in page.inner_text("#btnTol"), "default tolerance: " + page.inner_text("#btnTol"))
    page.click("#btnTol"); a = page.inner_text("#btnTol"); page.click("#btnTol"); b = page.inner_text("#btnTol"); page.click("#btnTol"); c = page.inner_text("#btnTol")
    check("10% + 2 mph" in a and "exact" in b and "+2 mph" in c.replace("10% + 2 mph", ""), f"the button cycles: {a} / {b} / {c}")
    page.click("#btnTol"); page.click("#btnTol")
    check(json.loads(page.evaluate("localStorage.getItem('kobd_overTol')")) == "exact", "choice saved")
    page.evaluate("window.__forceOver = 'over'; overUpdate()"); r = page.evaluate("(() => { const t = document.getElementById('t_speed'), c = getComputedStyle(t); return {s: c.boxShadow, bg: c.backgroundColor, anim: c.animationName, tr: c.transitionProperty}; })()")
    check("inset" in r["s"] and r["anim"] == "none", f"red = steady inset ring, no animation ({r['s'][:40]})")
    page.evaluate("window.__forceOver = null; overUpdate()"); check(cls(page) == [False, False], "highlight removed")

# ---------- end to end with mock GPS + OSM data (30 mph road for the first 150 m) ----------
def drive(page, kmh, gps_acc=None):
    page.evaluate(f"__mock.cruise = {kmh}; __mock.gps.dist = 0" + (f"; __mock.gps.acc = {gps_acc}" if gps_acc is not None else ""))

with app(gps={"permission": "granted"}, net={"overpass": overpass_fixture(), "weather": WEATHER}) as page:
    page.evaluate("localStorage.setItem('kobd_overTol', '\"p2\"'); tolUi(); __mock.cruise = 40; __mock.gps.speed = 6")
    connect(page); wait(page, "document.querySelector('#limit .rnd').textContent === '30'", 30000)
    page.click('nav button[data-p="drive"]'); page.wait_for_timeout(300)
    drive(page, 40)                                                      # 24.9 mph: under
    page.wait_for_timeout(2500); check(cls(page) == [False, False], "24.9 mph in a 30: no highlight")
    drive(page, 51)                                                      # 31.7 mph: amber band
    wait(page, "document.getElementById('t_speed').classList.contains('ovw')", 10000)
    page.wait_for_timeout(2500); check(cls(page) == [False, True], "31.7 mph (limit 30, +2 mph tolerance): amber, never red")
    drive(page, 60)                                                      # 37.3 mph: over
    page.wait_for_timeout(700); check(cls(page) == [False, True], "37.3 mph: still amber at first (red needs 2 s)")
    wait(page, "document.getElementById('t_speed').classList.contains('ovr')", 10000)
    samples = []
    for _ in range(6): page.wait_for_timeout(250); samples.append(cls(page))
    check(all(s == [True, False] for s in samples), "then steady red (no flashing between samples)")
    page.screenshot(path=str(OUT / "overlimit-red.png"))
    drive(page, 52)                                                      # 32.3 mph: under the red clear line (31.0)? no: 32.3 > 31 -> stays red
    page.wait_for_timeout(2500); check(cls(page)[0] is True, "32.3 mph: red holds (not yet 1 mph under limit + 2)")
    drive(page, 49)                                                      # 30.4 mph: clears to amber (> 29)
    wait(page, "!document.getElementById('t_speed').classList.contains('ovr')", 10000)
    page.wait_for_timeout(2000); check(cls(page) == [False, True], "30.4 mph: red cleared, amber (still over 30)")
    drive(page, 44)                                                      # 27.3 mph: clear
    wait(page, "!document.getElementById('t_speed').classList.contains('ovw')", 10000); check(cls(page) == [False, False], "27.3 mph: all clear")
    # accuracy
    drive(page, 60, gps_acc=25)                                          # fine fix (<= 35 m, roundel stays) but worse than 20 m
    page.wait_for_timeout(5500); check(cls(page) == [False, False] and page.is_visible("#limit"), "GPS accuracy 25 m (roundel shown): no highlight")
    drive(page, 60, gps_acc=8)
    wait(page, "document.getElementById('t_speed').classList.contains('ovr')", 15000); check(True, "accuracy 8 m: highlight comes on")
    # national limit / limit unknown
    check(page.evaluate("(() => { const keep = G.limit; G.limit = -1; overUpdate(); const a = document.getElementById('t_speed').classList.contains('ovr'); G.limit = null; overUpdate(); const b = document.getElementById('t_speed').classList.contains('ovr') || document.getElementById('t_speed').classList.contains('ovw'); G.limit = keep; return !a && !b; })()"), "national-limit roundel / unknown limit: never highlighted")
    page.click("#btnStop"); page.wait_for_timeout(500)
    check(cls(page) == [False, False], "Stop clears the highlight")
    check(not page.errors, "no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))

with app(gps={"permission": "granted"}, net={"overpass": {"elements": []}, "weather": WEATHER}) as page:     # no OSM data at all
    page.evaluate("__mock.cruise = 130; __mock.gps.speed = 20"); connect(page); page.wait_for_timeout(7000)
    check(not page.is_visible("#limit") and cls(page) == [False, False], "no limit data: no roundel, no highlight even at 81 mph")
