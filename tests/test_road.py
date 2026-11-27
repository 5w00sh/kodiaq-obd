"""Test 18 (v6.1.5): road data recorder (Stage 3 groundwork). Mock DeviceMotion: nothing recorded / no listener / no database when the setting is OFF; 1 Hz aggregated rows
(vertical RMS, peak-to-peak, max jerk, roll/pitch/yaw rate RMS, mean gravity, GPS, OBD speed, rpm) stored in IndexedDB; mount-noise sample at idle; storage cap with oldest-trip
eviction + warning; export per trip / all as CSV + JSON with a 'contains your GPS locations' confirmation; simulation isolation."""
import json
from common import app, check, OUT

def wait(page, expr, t=30000): page.wait_for_function(expr, timeout=t)
def connect(page):
    page.click("#btnConnect"); wait(page, "document.getElementById('status').textContent.includes('Connected')")
def dbs(page): return page.evaluate("indexedDB.databases().then(l => l.map(d => d.name))")
GPS = {"permission": "granted"}
PERM = ["accelerometer", "gyroscope"]

# ---------- motion access denied: the setting stays ON (v6.1.7), see test_v617.py ----------

# ---------- OFF (default): no listener, no rows, no database ----------
with app(motion=True, gps=GPS, permissions=PERM) as page:
    check(page.evaluate("RR.on") is False and "off" in page.evaluate("document.getElementById('btnRoad').textContent"), "default: Road mapping is off")
    connect(page); wait(page, "document.getElementById('status').textContent.includes('trip running')"); page.wait_for_timeout(4000)
    check(page.evaluate("__motion.listeners") == 0 and page.evaluate("RR.listening") is False, "OFF while connected and driving: no devicemotion listener attached")
    check("kobd_road" not in dbs(page) and page.evaluate("RR.curId()") is None, "OFF: no database was even created, no recording")
    check(not page.errors, "OFF: no JS errors")

# ---------- ON: rows ----------
with app(motion={"amp": 0.6, "freq": 2}, gps=GPS, permissions=PERM) as page:
    page.evaluate("__mock.cruise = 72")
    page.click('nav button[data-p="car"]'); page.click("#btnRoad"); wait(page, "document.getElementById('roadInfo').textContent.includes('while connected')", 10000)
    check(page.inner_text("#btnRoad") == "Road mapping: on" and page.evaluate("JSON.parse(localStorage.getItem('kobd_roadMap'))") is True and "while connected" in page.inner_text("#roadInfo"), "setting ON, saved on this device; says it records while connected")
    connect(page); wait(page, "document.getElementById('status').textContent.includes('trip running')")
    check(page.evaluate("__motion.listeners") == 1 and page.evaluate("RR.listening"), "ON + connected: one devicemotion listener")
    wait(page, "RR.rowsThisTrip >= 9", 40000)
    page.evaluate("__motion.spike = 14")                                         # one big pothole-like hit
    wait(page, "RR.rowsThisTrip >= 12", 20000)
    page.evaluate("RR.flush(true)"); page.wait_for_timeout(500)
    rows = page.evaluate("RR.rows(RR.curId())"); body = rows[2:]               # first rows: the gravity estimate is settling
    check(len(rows) >= 10, f"1 Hz rows stored in IndexedDB ({len(rows)})")
    r = rows[5]; spike = max(rows, key=lambda x: x["vPp"])
    check(40 <= r["n"] <= 55, f"~50 samples aggregated per row (n={r['n']})")
    check(abs(r["vRms"] - 0.6 / 2 ** .5) < 0.12 and 0.9 < r["vPp"] < 1.5, f"vertical accel: RMS {r['vRms']} (0.42 expected), peak-to-peak {r['vPp']} (1.2 expected)")
    check(4 < r["jerkMax"] < 14, f"max |jerk| {r['jerkMax']} m/s^3 (7.5 expected)")
    check(abs(r["rollRms"] - 5 / 2 ** .5) < 0.7 and abs(r["pitchRms"] - 3 / 2 ** .5) < 0.5 and abs(r["yawRms"] - 1) < 0.3, f"gyro RMS roll {r['rollRms']} pitch {r['pitchRms']} yaw {r['yawRms']}")
    check(abs(r["gx"] - 1.0) < 0.25 and abs(r["gz"] - 9.81) < 0.4, f"mean gravity vector ({r['gx']}, {r['gy']}, {r['gz']})")
    check(abs(r["lat"] - 51.4545) < 0.01 and r["acc"] == 8 and abs(r["speed"] - 72) < 2 and r["rpm"] > 300 and r["t"] % 1000 == 0, f"lat/lon/GPS accuracy/OBD speed/rpm/timestamp: {r['lat']}, {r['lon']}, ±{r['acc']} m, {r['speed']} km/h, {r['rpm']} rpm")
    check(spike["vPp"] > 8 and spike["jerkMax"] > 100, f"a single big hit shows up: peak-to-peak {spike['vPp']}, jerk {spike['jerkMax']}")
    # switching OFF mid-trip stops it
    n = page.evaluate("RR.rowsThisTrip"); page.click("#btnRoad"); page.wait_for_timeout(3500)
    check(page.evaluate("RR.listening") is False and page.evaluate("__motion.removed") >= 1, "turning OFF removes the listener")
    check(page.evaluate("RR.trips()")[0]["n"] >= n - 1, "rows recorded so far are kept")
    page.evaluate("RR.on = true; RR.sync()"); page.evaluate("RR.on = false; RR.sync()")
    # Demo never records
    page.click("#btnStop"); page.wait_for_timeout(600); page.evaluate("RR.on = true; store.set('roadMap', true)")
    page.click("#btnDemo"); page.wait_for_timeout(2500)
    check(page.evaluate("RR.listening") is False, "Demo with the setting ON: nothing recorded")
    page.click("#btnStop"); page.wait_for_timeout(400)
    check(not page.errors, "ON: no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))

# ---------- mount-noise sample (30 s at idle, stationary; shortened here) ----------
with app(motion={"amp": 0.2, "freq": 11}, gps=GPS, permissions=PERM) as page:
    page.evaluate("RR.on = true; store.set('roadMap', true); RR.noiseMs = 6000; RR.noiseSettle = 2; __mock.cruise = 0"); connect(page)
    page.evaluate("setInterval(() => RR.noises().then(n => { window.__nzN = n.length; }), 400)"); wait(page, "window.__nzN > 0", 45000)
    nz = page.evaluate("RR.noises()")[0]
    check(nz["n"] > 250 and len(nz["data"]) == nz["n"] * 7 and nz["cols"].startswith("dtMs,ax,ay,az") and 300 < nz["rpm"] < 1500, f"mount-noise sample stored: {nz['n']} raw samples at engine idle ({nz['rpm']} rpm), stationary")
    page.wait_for_timeout(4000); check(len(page.evaluate("RR.noises()")) == 1, "only one sample per trip")
    page.evaluate("__mock.cruise = 50")

# ---------- storage cap, export, delete ----------
with app(motion=True, gps=GPS, permissions=PERM) as page:
    dialogs = []; answer = {"accept": True}
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept() if answer["accept"] else d.dismiss()))
    mk = lambda k: [{"t": (1000 + k * 100 + i) * 1000, "lat": 51.5 + i * 1e-4, "lon": -2.6, "acc": 8, "speed": 50 + i % 7, "rpm": 1800, "n": 50, "vRms": 0.4 + i * 0.001, "vPp": 1.2, "jerkMax": 7.5, "rollRms": 3.5, "pitchRms": 2.1, "yawRms": 1.0, "gx": 1.0, "gy": 0.0, "gz": 9.81} for i in range(60)]
    page.evaluate("RR.CAP = 30000; RR.on = true")
    for k in range(5): page.evaluate("([k, rows]) => RR.put(1000 + k, rows[0].t, rows)", [k, mk(k)])
    left = page.evaluate("RR.trips().then(t => t.map(x => x.id))")
    check(len(left) <= 2 and left[-1] == 1004 and 1000 not in left, f"cap 30 KB: oldest trips evicted, newest kept ({left})")
    check("oldest" in page.inner_text("#roadInfo") and "deleted" in page.inner_text("#roadInfo"), "warning shown: " + page.inner_text("#roadInfo").split("⚠")[-1].strip()[:60])
    page.evaluate("RR.CAP = 50e6; RR.warn = ''"); page.evaluate("([k, rows]) => RR.put(2000, rows[0].t, rows)", [7, mk(7)]); page.click('nav button[data-p="car"]'); page.wait_for_timeout(500)
    check(page.locator(".rtrip").count() == 3 and page.is_enabled("#btnRoadAll"), "trips listed with Export / Delete buttons")
    n0 = len(page.evaluate("window.__exports || []"))
    answer["accept"] = False; page.locator(".rexp").first.click(); page.wait_for_timeout(600); answer["accept"] = True
    check(len(page.evaluate("window.__exports || []")) == n0, "cancelling the GPS-locations warning exports nothing")
    page.locator(".rexp").first.click(); page.wait_for_timeout(800)
    ex = page.evaluate("window.__exports"); names = [e["name"] for e in ex]
    check(any("GPS locations" in d for d in dialogs), "confirmation says the export contains your GPS locations")
    csv = next(e for e in ex if e["name"].endswith(".csv")); js = json.loads(next(e for e in ex if e["name"].endswith(".json"))["text"])
    lines = csv["text"].strip().split("\n")
    check(lines[0].startswith("trip,t,lat,lon,acc,speed,rpm,n,vRms,vPp,jerkMax,rollRms,pitchRms,yawRms,gx,gy,gz,touched") and len(lines) == 61, f"per-trip CSV: header + 60 rows ({len(lines)} lines), files {names[-2:]}")
    check(js["warning"] == "Contains GPS locations" and len(js["trips"]) == 1 and len(js["trips"][0]["rows"]) == 60 and js["trips"][0]["rows"][0]["lat"] == 51.5, "per-trip JSON: warning field, 60 rows with GPS")
    page.click("#btnRoadAll"); page.wait_for_timeout(800)
    allj = json.loads([e for e in page.evaluate("window.__exports") if e["name"].endswith(".json")][-1]["text"])
    check(len(allj["trips"]) == 3 and "mountNoise" in allj, f"export all: {len(allj['trips'])} trips + mount-noise samples, CSV + JSON")
    page.locator(".rdel").first.click(); page.wait_for_timeout(600)
    check(page.locator(".rtrip").count() == 2, "Delete removes one trip")
    page.click("#btnRoadDel"); page.wait_for_timeout(600)
    check(page.evaluate("RR.trips().then(t => t.length)") == 0 and page.is_disabled("#btnRoadAll"), "Delete all clears the store")
    check(not page.errors, "no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))

# ---------- simulation isolation ----------
with app(mock=False) as page:
    page.evaluate("sessionStorage.setItem('kobd_simMode', '1')"); page.reload(); page.wait_for_timeout(500)
    page.evaluate("RR.put(5, 5000000, [{t: 5000000, n: 50, vRms: 1}])"); page.wait_for_timeout(500)
    names = dbs(page); check("kobd_sim_road" in names and "kobd_road" not in names, f"simulation writes to kobd_sim_road only ({names})")
    page.click('nav button[data-p="log"]'); page.click("#simLeave"); page.wait_for_timeout(1500)
    check("kobd_sim_road" not in dbs(page), "leaving simulation deletes the sim road database")
