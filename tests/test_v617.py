"""Test 20 (v6.1.7): Road mapping / GPS auto-start + a denied permission keeps the setting ON, the `touched` flag (taps +-2 s, hidden/blur), export fixes
(mountNoise, units, schema), Speed tile has no overlapping elements (fullscreen button vs roundel/caption/digits/unit), the map finds road rows by time overlap
(merged trip, 3 segments), "View on map" in the Car tab, map after a service-worker update, a missing Leaflet file shows an error."""
import json, math, http.server, threading, functools
from playwright.sync_api import sync_playwright
from common import app, check, OUT, ROOT

def wait(page, expr, t=30000): page.wait_for_function(expr, timeout=t)
def connect(page):
    page.click("#btnConnect"); wait(page, "document.getElementById('status').textContent.includes('Connected')")
GPS = {"permission": "granted"}; PERM = ["accelerometer", "gyroscope"]
PERMJS = "window.__perm = 'granted'; DeviceMotionEvent.requestPermission = () => { window.__permCalls = (window.__permCalls || 0) + 1; return Promise.resolve(window.__perm); };"

# ---------- 1. auto-start ----------
with app(motion={"amp": 0.6}, gps=GPS, permissions=PERM) as page:
    page.context.add_init_script(PERMJS); page.reload(); page.wait_for_timeout(500)
    check(page.evaluate("RR.on") is False, "new device: Road mapping OFF by default")
    page.click('nav button[data-p="car"]'); page.click("#btnRoad"); page.wait_for_timeout(500)
    check(page.evaluate("RR.on") and page.evaluate("__permCalls") == 1, "turning it on asks for motion permission in the tap")
    page.reload(); page.wait_for_timeout(600)
    check(page.evaluate("RR.on") is True and "on" in page.evaluate("document.getElementById('btnRoad').textContent"), "setting survives a reload (kobd_roadMap)")
    page.evaluate("RR.perm = 'waiting'")                                          # a fresh page load: motion access not yet granted this session
    n = page.evaluate("window.__permCalls || 0"); connect(page)
    check(page.evaluate("window.__permCalls || 0") == n + 1, "Connect tap asks for motion permission itself (no extra tap)")
    wait(page, "RR.listening", 10000); check(page.evaluate("__motion.listeners") >= 1, "auto-started on connect: devicemotion listener attached")
    check(page.evaluate("store.get('gpsOn', true)") is True and page.evaluate("G.active"), "GPS auto-started on connect")
    page.click("#btnStop"); page.wait_for_timeout(500)
    check(page.evaluate("RR.on") is True, "Stop does not turn the setting off")
    page.reload(); page.wait_for_timeout(500)
    page.click("#btnDemo"); page.wait_for_timeout(2500)
    check(page.evaluate("RR.listening") is False and page.evaluate("RR.curId()") is None, "Demo: never records, setting stays on")
    check(not page.errors, "auto-start: no JS errors: " + "; ".join(page.errors))

# denied permission: the setting stays ON, message shown, retried
with app(motion={"amp": 0.6}, gps=GPS, permissions=PERM) as page:
    page.context.add_init_script(PERMJS.replace("'granted'", "'denied'", 1)); page.reload(); page.wait_for_timeout(500)
    page.click('nav button[data-p="car"]'); page.click("#btnRoad"); page.wait_for_timeout(600)
    check(page.evaluate("RR.on") is True and page.evaluate("JSON.parse(localStorage.getItem('kobd_roadMap'))") is True, "permission denied at the tap: saved setting stays ON")
    connect(page); page.wait_for_timeout(1500)
    check(page.evaluate("RR.on") is True and page.evaluate("RR.listening") is False, "denied: still on, nothing recorded")
    txt = page.inner_text("#roadInfo"); check("Road mapping: waiting for motion permission" in txt, "message: " + txt[:70])
    page.reload(); page.wait_for_timeout(500); check(page.evaluate("RR.on") is True, "denied + reload: setting still ON")
    page.evaluate("window.__perm = 'granted'; RR.perm = 'waiting'"); connect(page)
    wait(page, "RR.listening", 10000); check(True, "permission granted later (next Connect tap): starts by itself")
    # retry without a tap
    page.click("#btnStop"); page.wait_for_timeout(300); page.evaluate("window.__perm = 'denied'; RR.perm = 'waiting'"); connect(page); page.wait_for_timeout(500)
    page.evaluate("window.__perm = 'granted'"); wait(page, "RR.listening", 25000); check(True, "waiting state retries by itself and starts when allowed")
    check(page.evaluate("store.get('roadMapLog', []).length") >= 1, "every change of the saved setting is logged with its reason")
    check(not page.errors, "denied flow: no JS errors: " + "; ".join(page.errors))

# ---------- 2. touched flag ----------
with app(motion={"amp": 0.6}, gps=GPS, permissions=PERM) as page:
    page.evaluate("RR.on = true; store.set('roadMap', true); __mock.cruise = 60"); connect(page)
    ct = page.evaluate("Math.floor(Date.now() / 1000)"); wait(page, "RR.rowsThisTrip >= 6", 40000)        # (the Connect click itself is a real tap: ignore rows near it)
    s0 = page.evaluate("(() => { const s = Math.floor(Date.now() / 1000); window.dispatchEvent(new Event('pointerdown')); return s; })()")
    wait(page, "RR.rowsThisTrip >= 14", 40000)
    page.evaluate("RR.flush(true)"); page.wait_for_timeout(400)
    rows = [r for r in page.evaluate("RR.rows(RR.curId())") if r["t"] // 1000 > ct + 2]
    bad = [r["t"] // 1000 - s0 for r in rows if bool(r["touched"]) != (abs(r["t"] // 1000 - s0) <= 2)]
    near = sorted(r["t"] // 1000 - s0 for r in rows if r["touched"])
    check(not bad and len(near) >= 3 and all(abs(d) <= 2 for d in near), f"a tap flags exactly the rows within +-2 s (touched offsets {near}, mismatches {bad})")
    check(all(r["touched"] is False for r in rows if r["t"] // 1000 < s0 - 2) and any(r["t"] // 1000 < s0 - 2 for r in rows), "rows well before and after the tap are untouched")
with app(motion={"amp": 0.6}, gps=GPS, permissions=PERM) as page:
    page.evaluate("RR.on = true; store.set('roadMap', true); __mock.cruise = 60"); connect(page)
    ct = page.evaluate("Math.floor(Date.now() / 1000)"); wait(page, "RR.rowsThisTrip >= 6", 40000)
    h0 = page.evaluate("(() => { Object.defineProperty(document, 'hidden', {value: true, configurable: true}); document.dispatchEvent(new Event('visibilitychange')); return Math.floor(Date.now() / 1000); })()")
    page.wait_for_timeout(2300)
    h1 = page.evaluate("(() => { Object.defineProperty(document, 'hidden', {value: false, configurable: true}); document.dispatchEvent(new Event('visibilitychange')); return Math.floor(Date.now() / 1000); })()")
    wait(page, "RR.rowsThisTrip >= 14", 40000); page.evaluate("RR.flush(true)"); page.wait_for_timeout(400)
    rows = [r for r in page.evaluate("RR.rows(RR.curId())") if r["t"] // 1000 > ct + 2]; tl = sorted(r["t"] // 1000 for r in rows if r["touched"])
    check(len(tl) >= 2 and tl[0] >= h0 and tl[-1] <= h1 and all(r["touched"] for r in rows if h0 <= r["t"] // 1000 <= h1), f"hidden page flags exactly its seconds ({h0}..{h1}: {[t - h0 for t in tl]})")
    check(any(not r["touched"] for r in rows), "other rows stay untouched")
    check(not page.errors, "touched: no JS errors: " + "; ".join(page.errors))

# ---------- 3. export: mountNoise, units, schema ----------
def mkrows(t0, n=20): return [{"t": t0 + i * 1000, "lat": 51.5 + i * 1e-4, "lon": -2.6, "acc": 8, "speed": 50, "rpm": 1800, "n": 50, "vRms": 0.4, "vPp": 1.2, "jerkMax": 7.5, "rollRms": 3.5, "pitchRms": 2.1, "yawRms": 1, "gx": 1, "gy": 0, "gz": 9.8, "touched": i == 3} for i in range(n)]
PUTN = "([id, tripId]) => new Promise(res => { const r = indexedDB.open(KP + 'road', 1); r.onsuccess = () => { const t = r.result.transaction('noise', 'readwrite'); t.objectStore('noise').put({id, t: id, tripId, rpm: 800, coolant: 85, n: 2, cols: 'dtMs,ax,ay,az,alpha,beta,gamma', bytes: 100, data: [20,1,0,9.8,0,0,0, 20,1,0,9.8,0,0,0]}); t.oncomplete = () => res(); }; })"
with app(motion=True, gps=GPS, permissions=PERM) as page:
    page.on("dialog", lambda d: d.accept())
    page.evaluate("([a, b, c]) => RR.put(1000, a[0].t, a).then(() => RR.put(2000, b[0].t, b))", [mkrows(5_000_000), mkrows(9_000_000), 0])
    page.evaluate(PUTN, [111, 1000]); page.evaluate(PUTN, [222, None]); page.click('nav button[data-p="car"]'); page.evaluate("RR.view()"); page.wait_for_timeout(500)
    check("mount-noise samples: 2" in page.inner_text("#roadInfo"), "Car tab shows 2 mount-noise samples")
    page.click("#btnRoadAll"); page.wait_for_timeout(700)
    j = json.loads([e for e in page.evaluate("window.__exports") if e["name"].endswith(".json")][-1]["text"])
    check(len(j["mountNoise"]) == 2 and j["schema"] == 2, f"Export all: mountNoise has {len(j['mountNoise'])} samples, schema {j['schema']}")
    u = j["units"]; check(u["speed"].startswith("km/h") and u["vRms"] == "m/s²" and u["rollRms"] == "deg/s" and u["acc"].startswith("m") and "touched" in j["cols"] and "units" in j["mountNoiseUnits"] or "ax" in j["mountNoiseUnits"], f"units in the header: speed {u['speed']}, accel {u['vRms']}, gyro {u['rollRms']}, acc {u['acc']}")
    page.locator('.rexp[data-id="1000"]').click(); page.wait_for_timeout(700)
    j = json.loads([e for e in page.evaluate("window.__exports") if e["name"].endswith(".json")][-1]["text"])
    check([n["id"] for n in j["mountNoise"]] == [111], "per-trip export: the sample linked to the trip")
    page.locator('.rexp[data-id="2000"]').click(); page.wait_for_timeout(700)
    j = json.loads([e for e in page.evaluate("window.__exports") if e["name"].endswith(".json")][-1]["text"])
    check([n["id"] for n in j["mountNoise"]] == [222], "per-trip export with no linked sample: the newest one")
    csv = [e for e in page.evaluate("window.__exports") if e["name"].endswith(".csv")][-1]["text"].split("\n")
    check(csv[0].endswith(",touched") and csv[1].endswith(",false"), "CSV carries touched")
    check(not page.errors, "export: no JS errors: " + "; ".join(page.errors))

# ---------- 4. Speed tile: no overlapping elements ----------
OVL = """() => {
  const t = document.getElementById('t_speed'), v = t.querySelector('.val'), els = {};
  const rg = n => { const r = document.createRange(); r.selectNode(n); return r.getBoundingClientRect(); };
  els.button = document.getElementById('btnBig').getBoundingClientRect(); els.roundel = t.querySelector('.rnd').getBoundingClientRect(); els.caption = t.querySelector('.limit small').getBoundingClientRect();
  els.digits = rg(v.firstChild); els.unit = rg(v.querySelector('.unit'));
  const k = Object.keys(els).filter(n => els[n].width > 0 && els[n].height > 0), bad = [], tr = t.getBoundingClientRect();
  for (let i = 0; i < k.length; i++) for (let j = i + 1; j < k.length; j++) { const a = els[k[i]], b = els[k[j]];
    if (a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5) bad.push(k[i] + ' x ' + k[j]); }
  const bt = els.button; if (bt.left < tr.left || bt.right > tr.right || bt.bottom > tr.bottom + 0.5 || bt.top < tr.top) bad.push('button outside the tile');
  return {bad, seen: k};
}"""
VPS = [(360, 760), (412, 915), (800, 1280), (1280, 800), (800, 1100), (1280, 700)]
for theme in ("night", "day"):
    for w, h in VPS:
        with app(viewport=(w, h), mock=False, theme=theme) as page:
            page.click("#btnDemo"); page.wait_for_timeout(2200)
            for lab, js in (("no limit", ""), ("limit 30", "limitUi(30)"), ("national limit", "limitUi(-1)")):
                if js: page.evaluate(js); page.wait_for_timeout(120)
                for big in (False, True):
                    if big != page.evaluate("document.getElementById('p_drive').classList.contains('big')"): page.click("#btnBig"); page.wait_for_timeout(300)
                    r = page.evaluate(OVL)
                    check(not r["bad"] and "button" in r["seen"] and ("roundel" in r["seen"]) == bool(js), f"{theme} {w}x{h} {lab}{' big' if big else ''}: no overlap in the Speed tile ({', '.join(r['seen'])})" + ("" if not r["bad"] else ": " + "; ".join(r["bad"])))
            if (w, h) in ((360, 760), (412, 915)): page.evaluate("limitUi(30)"); page.screenshot(path=str(OUT / f"v617-speedtile-{theme}-{w}x{h}.png"))
            check(not page.errors, "no JS errors")

# ---------- 5. map: time overlap, View on map, sw update, missing Leaflet ----------
def seg(t0, lat0, n=60): return [{"t": t0 + i * 1000, "lat": round(lat0 + i * 0.0002, 6), "lon": -2.6 + i * 0.0001, "acc": 8, "speed": 50, "rpm": 1800, "n": 50, "vRms": 0.4, "vPp": 1.2, "jerkMax": 7.5, "rollRms": 3, "pitchRms": 2, "yawRms": 1, "gx": 1, "gy": 0, "gz": 9.8, "touched": False} for i in range(n)]
T0 = 1_700_000_000_000
MERGED = {"date": __import__("datetime").datetime.utcfromtimestamp(T0 / 1000).isoformat() + ".000Z", "miles": 5.0, "litres": 0.4, "mpg": 45.0, "per10": 1, "score": 80, "rr": T0 + 7, "end": T0 + 400_000}   # rr id matches NO road trip
OLD = dict(MERGED, date=__import__("datetime").datetime.utcfromtimestamp((T0 + 5_000_000) / 1000).isoformat() + ".000Z", rr=None); OLD.pop("end")
def setup(page):
    page.evaluate("([m, o]) => { store.set('trips', [o, m]); tripsCache = store.get('trips', []); renderLearned(); }", [MERGED, OLD])
    page.evaluate("RR.put(1, 1700000000000, [])")
    for i, (t, la) in enumerate(((T0, 51.45), (T0 + 100_000, 51.47), (T0 + 250_000, 51.49))): page.evaluate("([id, t, r]) => RR.put(id, t, r)", [T0 + 10 + i, t, seg(t, la)]) if False else page.evaluate("([t, r]) => RR.put(t, t, r)", [t + 10, seg(t, la)])
    # old trip (no end): three segments chained inside the 10 min merge window
    for t, la in ((T0 + 5_000_000, 51.45), (T0 + 5_100_000, 51.47)): page.evaluate("([t, r]) => RR.put(t, t, r)", [t + 10, seg(t, la)])
    page.evaluate("RR.del(1)")
with app(viewport=(412, 915), mock=False, net={"tiles": True}) as page:
    setup(page); page.click('nav button[data-p="style"]'); page.wait_for_timeout(500)
    page.locator("#trips .trip").nth(0).click(); wait(page, "window.__mapPts > 0", 15000)
    check(page.evaluate("window.__mapPts") == 180, f"merged trip (rr id matches nothing, 3 road segments): the map shows all rows ({page.evaluate('window.__mapPts')} of 180)")
    page.click("#mapClose"); page.locator("#trips .trip").nth(1).click(); wait(page, "window.__mapPts == 120", 15000)
    check(True, "older trip without an end time: the segments inside the 10 min merge window are joined (120 rows)")
    page.click("#mapClose"); page.click('nav button[data-p="car"]'); page.wait_for_timeout(500)
    check(page.locator(".rmap").count() >= 3, "Car tab road list: 'View on map' button on every trip")
    ok = page.evaluate("""() => { const b = document.querySelector('.rtrip'); const r = b.getBoundingClientRect(), p = b.parentElement.getBoundingClientRect(); return [...b.querySelectorAll('button')].every(x => x.getBoundingClientRect().right <= p.right + 1 && x.getBoundingClientRect().height >= 36); }""")
    check(ok, "the three row buttons fit and are tappable")
    page.locator(".rmap").first.click(); wait(page, "document.getElementById('mapView').classList.contains('show') && window.__mapPts > 0", 15000)
    check(page.evaluate("!!window.L && !!MapUI.map"), "View on map opens the map")
    page.screenshot(path=str(OUT / "v617-viewonmap.png")); page.click("#mapClose")
with app(viewport=(412, 915), mock=False, net={"tiles": True}) as page:      # Leaflet file missing -> visible error
    setup(page); page.route("**/vendor/leaflet.js", lambda r: r.abort()); page.click('nav button[data-p="style"]'); page.wait_for_timeout(400)
    page.locator("#trips .trip").nth(0).click(); page.wait_for_timeout(1500)
    m = page.inner_text("#mapBox"); check("map library could not be loaded" in m, f"missing Leaflet: visible error '{m[:60]}'")
# live (still running) trip
with app(motion={"amp": 0.6}, gps=GPS, permissions=PERM) as page:
    page.evaluate("RR.on = true; store.set('roadMap', true); __mock.cruise = 60"); connect(page); wait(page, "RR.rowsThisTrip >= 4", 40000)
    page.click('nav button[data-p="car"]'); page.wait_for_timeout(400); page.locator(".rmap").first.click(); page.wait_for_timeout(2500)
    t = page.inner_text("#mapTitle") + " | " + page.inner_text("#mapBox")
    check("still running" in t, f"a trip still being recorded: map opens live / says so ('{t[:70]}')")
    page.click("#mapClose")

# sw update then map
BUILD = {"n": 1}
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k): pass
    def do_GET(self):
        if self.path.split("?")[0] == "/sw.js":
            body = (ROOT / "sw.js").read_bytes() + f"\n// test build {BUILD['n']}\n".encode()
            self.send_response(200); self.send_header("Content-Type", "text/javascript"); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body); return
        super().do_GET()
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
with sync_playwright() as p:
    b = p.chromium.launch(); c = b.new_context(viewport={"width": 412, "height": 915}, service_workers="allow")
    c.add_init_script("window.__KOBD_SW = true; try{ if(!localStorage.getItem('kobd_splashDay')) localStorage.setItem('kobd_splashDay', new Date().toLocaleDateString('sv')); }catch(e){}")
    page = c.new_page(); errs = []; page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(f"http://127.0.0.1:{srv.server_port}/index.html"); page.wait_for_function("navigator.serviceWorker.controller != null", timeout=20000)
    page.wait_for_function("caches.keys().then(k => k.length > 0)"); page.wait_for_timeout(800)
    cached = page.evaluate("caches.keys().then(async ks => { const c = await caches.open(ks[0]); return (await c.keys()).map(r => new URL(r.url).pathname); })")
    check("/vendor/leaflet.js" in cached and "/vendor/leaflet.css" in cached, f"Leaflet files precached by sw.js ({[x for x in cached if 'vendor' in x]})")
    setup(page); BUILD["n"] = 2
    page.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update())"); page.wait_for_selector("#updToast.show", timeout=20000)
    page.evaluate("window.__marker = 1"); page.click("#updToast"); page.wait_for_function("window.__marker === undefined", timeout=20000); page.wait_for_timeout(1000)
    cached = page.evaluate("caches.keys().then(async ks => { const c = await caches.open(ks[0]); return (await c.keys()).map(r => new URL(r.url).pathname); })")
    check("/vendor/leaflet.js" in cached, "after the update the new cache still has Leaflet")
    page.click('nav button[data-p="style"]'); page.wait_for_timeout(400); page.locator("#trips .trip").nth(0).click(); page.wait_for_function("window.__mapPts > 0", timeout=15000)
    check(page.evaluate("!!window.L") and page.evaluate("window.__mapPts") == 180, "map opens after a simulated service-worker update (Leaflet loaded, 180 rows)")
    check(not errs, "no JS errors: " + "; ".join(errs)); b.close()
srv.shutdown()
