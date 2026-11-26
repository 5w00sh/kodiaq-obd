"""Test 7: split Fuel hero (range + @NN mpg basis, remaining litres/% + £ to full), range basis rules, low-fuel colours, smoothing,
Big-mode hot-coolant rule, auto fill-up detection + receipt prompt."""
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
    num = int(page.inner_text("#t_range .num"))
    check(abs(num - left/0.10) <= 3, f"Range tile: {num} mi  (40.6 L at 0.10 L/mi = {left/0.10:.0f} mi; the gauge is 8-bit so +/-1 is fine)")
    check(page.inner_text("#t_range .basis").strip() == "@45 mpg", f"basis shown on the tile: {page.inner_text('#t_range .basis')} (0.10 L/mi = 45.5 mpg)")
    check(page.inner_text("#remL").strip() == "41 L (70%)", f"Estimated remaining: {page.inner_text('#remL')}")
    check(page.inner_text("#remCost").strip() == f"£{round((58-left)*1.45)} to full", f"{page.inner_text('#remCost')}  (litres to full x saved diesel price)")
    check(page.inner_text("#t_range .lab").strip().lower() == "range" and page.inner_text("#t_remain .lab").strip().lower() == "estimated remaining", "labels: Range / Estimated remaining")
    check(page.locator("#t_miles").count() == 0 and page.locator("#fuelhero #t_range").count() == 1, "no separate small Range tile; Range + Remaining live in the split Fuel hero")
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

# ---------------- range basis: 50+ miles -> last 50; fewer -> all-time trip average (even short trips); none -> 40 mpg ----------------
with app() as page:
    page.evaluate("FUEL_WIN_MS = 6000"); connect(page); wait(page, "fuelMed != null", 15000)
    r = page.evaluate("rangeInfo()")
    check(r["basis"] == "40 mpg assumed" and abs(r["mpg"] - 40) < .01, f"no trips yet: 40 mpg assumed, not 45 ({r['miles']:.0f} mi)")
    check(page.inner_text("#t_range .basis").strip() == "@40 mpg", "tile shows '@40 mpg'")
    page.evaluate("tripOpen = true; trip.km = 16.09344; trip.L = 1.2")             # a 10-mile trip in progress does NOT change the basis any more
    check(page.evaluate("rangeInfo().basis") == "40 mpg assumed", "an unsaved trip in progress does not replace the 40 mpg default")
with app() as page:
    seed(page, [trip(1, 2.0, 0.125), trip(2, 0.3, 0.125)])                          # only 2.3 miles of history, short trips
    page.evaluate("FUEL_WIN_MS = 6000"); connect(page); wait(page, "fuelMed != null", 15000)
    r = page.evaluate("rangeInfo()")
    check(r["basis"] == "all-time average" and abs(r["lpm"] - 0.125) < .004, f"under 50 miles: all-time trip average ({r['mpg']:.1f} mpg) even from short trips")
    check(page.inner_text("#t_range .basis").strip() == "@36 mpg", f"tile: {page.inner_text('#t_range .basis')}")
with app() as page:
    seed(page, [trip(i, 12, 0.20) for i in range(1, 5)])                            # 48 miles: still under 50 -> all-time
    page.evaluate("FUEL_WIN_MS = 6000"); connect(page); wait(page, "fuelMed != null", 15000)
    check(page.evaluate("consumption().basis") == "all-time average", "48 miles: still the all-time average")
    page.evaluate("tripsCache.push({miles: 4, litres: 0.4, mpg: 45})")              # 52 miles now; the newest 50 = 4 mi at 0.10 + 46 mi at 0.20
    c = page.evaluate("consumption()")
    check(c["basis"] == "last 50 mi" and abs(c["lpm"] - (0.4 + 46*0.2)/50) < .002, f"50+ miles: last 50 miles rate ({c['mpg']:.1f} mpg)")

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

# ---------------- Big mode: coolant only when hot (> 105 C), in fuel flow's place ----------------
with app() as page:
    seed(page, recent, big=True)
    page.evaluate("FUEL_WIN_MS = 4000"); connect(page); wait(page, "fuelMed != null", 15000)
    def state(c):
        page.evaluate(f"__mock.coolantC = {c}"); page.wait_for_timeout(2800)
        return page.is_visible("#t_coolant"), page.is_visible("#t_lph"), page.is_visible("#t_range")
    check(state(90) == (False, True, True), "Big mode, coolant 90 C (normal): coolant hidden, fuel flow + range shown")
    check(state(104) == (False, True, True), "104 C (hot-ish, not over 105): still hidden")
    check(state(106) == (True, False, True), "106 C: coolant appears in fuel flow's place, range stays")
    check("hot" in page.evaluate("document.getElementById('t_coolant').className") and page.inner_text("#t_coolant .val").split()[0] == "106", "and it is shown amber")
    page.screenshot(path=str(OUT / "fuel-big-hot.png"))
    check(state(104) == (True, False, True), "104 C: stays (hysteresis, no flicker)")
    check(state(102) == (False, True, True), "102 C: gone again")
    page.click("#btnBig"); page.wait_for_timeout(400)
    check(page.is_visible("#t_coolant") and page.is_visible("#t_lph") and page.is_visible("#t_range") and page.is_visible("#t_remain"), "normal mode: coolant, fuel flow, range and remaining all on screen")

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
    check(page.inner_text("#t_range .num").isdigit() and "£" in page.inner_text("#remCost"), "Demo shows a range and £ to full")
    check(ls(page, "fuelLast") is None and ls(page, "fillPending") is None, "demo never writes fuel history or fills")
    page.click("#btnStop")
    check(not page.errors, "no JS errors " + "; ".join(page.errors))
