"""Test 7: fuel left, range, low-fuel colours, smoothing, Big-mode coolant/range swap, auto fill-up detection + receipt prompt."""
import json, time
from common import app, check, OUT

def ls(page, key): return json.loads(page.evaluate(f"localStorage.getItem('kobd_{key}') || 'null'"))
def wait(page, expr, t=20000): page.wait_for_function(expr, timeout=t)
def connect(page):
    page.click("#btnConnect"); wait(page, "document.getElementById('status').textContent.includes('Connected')")
def trip(i, miles, lpm): return {"date": f"2026-11-{i:02d}T08:00:00Z", "miles": miles, "litres": round(miles*lpm, 2), "mpg": 4.54609/lpm, "per10": 1, "score": 80}
def seed(page, trips=None, **kv):
    """Pre-load localStorage before the page scripts run (the old page's pagehide handler would overwrite a plain write)."""
    items = dict(kv)
    if trips: items["trips"] = trips
    page.context.add_init_script(f"for (const [k, v] of Object.entries({json.dumps(items)})) localStorage.setItem('kobd_' + k, JSON.stringify(v));")
    page.reload(); page.wait_for_timeout(400)
def tile(page): return " ".join(page.inner_text("#t_range .val").split())

# ---------------- range from recent trips, all-time average, cost to fill ----------------
older = [trip(i, 12, 0.15) for i in range(1, 5)]            # 48 mi at 0.15 L/mi
recent = [trip(i, 12, 0.10) for i in range(5, 10)]          # 60 mi at 0.10 L/mi: the last 50 miles are all 0.10
with app() as page:
    seed(page, older + recent, price=1.45)
    page.evaluate("FUEL_WIN_MS = 6000; __mock.fuelPct = 70")
    connect(page); wait(page, "fuelMed != null", 15000); page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT / "fuel-drive.png"))
    left = 70 * 58 / 100
    t = tile(page)
    check(abs(int(t.split()[0]) - left/0.10) <= 3, f"Drive Range tile: {t}  (40.6 L at 0.10 L/mi = {left/0.10:.0f} mi; the gauge is 8-bit so +/-1 is fine)")
    check(f"{round(left)} L" in t, "tile shows litres left small beside the miles")
    check(page.inner_text("#t_range .lab").strip().lower() == "range" and not page.is_visible("#t_miles"), "Range tile replaced the Trip-miles tile")
    page.click('nav button[data-p="fuel"]'); page.wait_for_timeout(500)
    info = page.inner_text("#rangeInfo")
    page.screenshot(path=str(OUT / "fuel-tab.png"))
    check("last 50 mi" in info and "all-time average" in info, "Fuel tab: range from last 50 miles + all-time average")
    allm = left / ((60*0.10 + 48*0.15) / 108)
    import re
    got = int(re.search(r"all-time average: (\d+) mi", info).group(1))
    check(abs(got - allm) <= 3, f"all-time range {got} mi (expected about {allm:.0f})")
    cost = float(re.search(r"£(\d+\.\d\d) at", info).group(1))
    check(abs(cost - (58-left)*1.45) < 0.3, f"cost to fill at £1.45/L: £{cost:.2f}")
    check(page.evaluate("rangeInfo().basis") == "last 50 mi", "basis: last 50 mi")
    check(not page.errors, "no JS errors " + "; ".join(page.errors))

# ---------------- fallbacks: this trip, then 45 mpg ----------------
with app() as page:
    page.evaluate("FUEL_WIN_MS = 6000"); connect(page); wait(page, "fuelMed != null", 15000)
    r = page.evaluate("rangeInfo()")
    check(r["basis"] == "45 mpg assumed" and abs(r["mpg"] - 45) < .01, f"no trips yet: falls back to 45 mpg ({r['miles']:.0f} mi)")
    page.evaluate("tripOpen = true; trip.km = 16.09344; trip.L = 1.2")         # 10 miles, 1.2 L = 0.12 L/mi
    r = page.evaluate("rangeInfo()")
    check(r["basis"] == "this trip" and abs(r["lpm"] - 0.12) < .001, f"then this trip's own rate ({r['lpm']:.3f} L/mi)")

# ---------------- low fuel colours ----------------
with app() as page:
    seed(page, recent)
    page.evaluate("FUEL_WIN_MS = 4000"); connect(page); wait(page, "fuelMed != null", 15000)
    for pct, cls, label in ((70, None, "plenty"), (13, "hot", "13% = 7.5 L = 75 mi: amber"), (6, "crit", "6% = 3.5 L = 35 mi: red")):
        page.evaluate(f"__mock.fuelPct = {pct}; fuelWin = []"); page.wait_for_timeout(5500)
        c = page.evaluate("document.getElementById('t_range').className")
        check((cls in c) if cls else ("hot" not in c and "crit" not in c), f"{label}: tile class '{c}'")
        if cls: page.screenshot(path=str(OUT / f"fuel-low-{cls}.png"))

# ---------------- smoothing: spikes of +/-15 % and hard braking do not move the number ----------------
with app() as page:
    seed(page, recent)
    page.evaluate("FUEL_WIN_MS = 90000; __mock.fuelPct = 60; __mock.fuelSpike = 15")
    connect(page); wait(page, "fuelMed != null", 15000); page.wait_for_timeout(3000)
    seen = []
    for _ in range(14):
        seen.append(page.evaluate("rangeInfo().left")); page.wait_for_timeout(700)
    check(max(seen) - min(seen) <= 0.6, f"litres left steady at {min(seen):.1f}-{max(seen):.1f} L through +/-15 % gauge spikes (raw would swing +/-8.7 L)")
    raw = page.evaluate("latest.fuel"); check(raw is not None, f"(raw reading right now: {raw:.0f} %)")
    n = page.evaluate("fuelWin.length"); page.evaluate("fuelFreezeUntil = performance.now() + 4000"); page.wait_for_timeout(2500)
    check(page.evaluate("fuelWin.length") == n, "samples ignored while frozen (hard braking / accelerating)")

# ---------------- Big mode: range replaces coolant when warm, coolant comes back when cold/hot ----------------
with app() as page:
    seed(page, recent, big=True)
    page.evaluate("FUEL_WIN_MS = 4000"); connect(page); wait(page, "fuelMed != null", 15000)
    def state(c):
        page.evaluate(f"__mock.coolantC = {c}"); page.wait_for_timeout(2800)
        return page.is_visible("#t_range"), page.is_visible("#t_coolant")
    check(state(60) == (False, True), "Big mode, coolant 60 C (warming up): coolant tile")
    check(state(90) == (True, False), "Big mode, coolant 90 C (normal): range tile replaces coolant")
    page.screenshot(path=str(OUT / "fuel-big-range.png"))
    check(state(74) == (True, False), "74 C: stays on range (hysteresis, no flicker)")
    check(state(106) == (False, True), "106 C (hot): coolant is back")
    check(page.inner_text("#t_coolant .val").split()[0] == "106" and "hot" in page.evaluate("document.getElementById('t_coolant').className"), "and it is shown amber")
    check(state(90) == (True, False), "back to 90 C: range again")
    page.click("#btnBig"); page.wait_for_timeout(300)
    check(page.is_visible("#t_range") and page.is_visible("#t_coolant"), "normal mode: Range and Coolant tiles both on screen")

# ---------------- auto fill-up: engine off -> on, +55 points while stationary ----------------
with app() as page:
    seed(page, recent, fuelLast={"pct": 30, "t": int(time.time()*1000) - 3600000}, fillStarted=True, sinceFill={"km": 160.9, "L": 9.0}, cal=1.0)
    page.evaluate("FUEL_WIN_MS = 5000; __mock.fuelPct = 97; __mock.cruise = 60")          # refuelled while off; now driving off at once
    connect(page); wait(page, "fuelMed != null", 15000)
    check(ls(page, "fillPending") is not None, "fill detected at engine start: " + json.dumps(ls(page, "fillPending")))
    p = ls(page, "fillPending"); check(abs(p["estL"] - 38.9) < 1.0 and p["before"] == 30 and p["after"] == 97, f"estimate {p['estL']} L (gauge 30% -> 97% of 58 L)")
    check("Fill-up detected" in page.inner_text("#log"), "logged in the adapter log")
    page.wait_for_timeout(11000)
    check(not page.is_visible("#fillCard"), "never prompts while moving (60 km/h for 11 s)")
    page.evaluate("__mock.cruise = 0"); wait(page, "document.getElementById('fillCard').classList.contains('show')", 20000)
    check(True, "stationary for 8 s: the prompt appears")
    txt = page.inner_text("#fillCard")
    check("about 39 L" in txt and "Litres from receipt" in page.get_attribute("#fillLit", "placeholder"), "prompt: " + " ".join(txt.split()))
    page.screenshot(path=str(OUT / "fuel-fillcard.png"))
    page.click('nav button[data-p="drive"]')
    page.fill("#fillLit", "")
    page.click("#fillSave"); page.wait_for_timeout(200)
    check(page.is_visible("#fillCard") and ls(page, "fillPending") is not None, "Save with no litres does nothing")
    page.evaluate("__mock.cruise = 60"); page.wait_for_timeout(1500)
    check(not page.is_visible("#fillCard"), "card hides the moment you move off, and is kept pending")
    check(ls(page, "fillPending") is not None, "pending survives")
    page.evaluate("__mock.cruise = 0"); wait(page, "document.getElementById('fillCard').classList.contains('show')", 20000)
    page.fill("#fillLit", "10.8"); page.click("#fillSave"); page.wait_for_timeout(300)
    check(not page.is_visible("#fillCard") and ls(page, "fillPending") is None, "receipt saved, card gone")
    cal = ls(page, "cal"); fills = ls(page, "fills")
    check(abs(cal - 1.1) < 0.01 and len(fills) == 1, f"near-full fill feeds the pump calibration (x{cal:.3f}, {len(fills)} fill in history)")
    check(ls(page, "autoFills")[-1]["receipt"] == 10.8, "receipt stored with the detected fill")
    page.click('nav button[data-p="fuel"]'); page.wait_for_timeout(300)
    check("Last detected fill" in page.inner_text("#fillInfo"), "Fuel tab lists the detected fill")
    check(not page.errors, "no JS errors " + "; ".join(page.errors))

# partial fill (to 70 %): logged, receipt kept, but NOT used for calibration (not a brim)
with app() as page:
    seed(page, recent, fuelLast={"pct": 30, "t": int(time.time()*1000) - 3600000}, fillStarted=True, sinceFill={"km": 160.9, "L": 9.0}, cal=1.0)
    page.evaluate("FUEL_WIN_MS = 5000; __mock.fuelPct = 70; __mock.cruise = 0")
    connect(page); wait(page, "document.getElementById('fillCard').classList.contains('show')", 30000)
    page.fill("#fillLit", "22.5"); page.click("#fillSave"); page.wait_for_timeout(300)
    check(ls(page, "cal") == 1.0 and not ls(page, "fills"), "partial fill (70 %): logged but calibration untouched")
    check(ls(page, "autoFills")[-1]["receipt"] == 22.5, "receipt stored")

# during a drive: a fast 40-point jump within 10 minutes is still caught; a normal slow burn never triggers
with app() as page:
    seed(page, recent, fuelLast={"pct": 60, "t": int(time.time()*1000)})
    page.evaluate("FUEL_WIN_MS = 5000; __mock.fuelPct = 60; __mock.fuelBurn = 4; __mock.cruise = 0")    # 4 %/min: faster than any real car
    connect(page); wait(page, "fuelMed != null", 15000); page.wait_for_timeout(9000)
    check(ls(page, "fillPending") is None, "falling fuel never triggers a fill")
    page.evaluate("__mock.fuelBurn = 0; __mock.fuelPct = 85"); page.wait_for_timeout(14000)
    check(ls(page, "fillPending") is not None and ls(page, "fillPending")["after"] >= 80, "jump while connected is detected too")

# demo and unsupported fuel: quiet
with app(mock=False) as page:
    page.click("#btnDemo"); page.wait_for_timeout(5000)
    check(page.inner_text("#t_range .val").split()[0].isdigit(), "Demo shows a range")
    check(ls(page, "fuelLast") is None and ls(page, "fillPending") is None, "demo never writes fuel history or fills")
    page.click("#btnStop")
    check(not page.errors, "no JS errors " + "; ".join(page.errors))
