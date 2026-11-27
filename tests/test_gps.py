"""Test 7: phone GPS end to end against the mock: permission asked once, GPS only while connected, GPS-vs-OBD speed error,
hill gradient + ascent, OSM speed limit change (30 -> 60 mph) with % over, a GPS dropout mid-trip, weather at trip start,
route + features saved with the trip, privacy of look-ups, cache works offline, 'no data' stays quiet."""
import json
from common import app, check, OUT, overpass_fixture, WEATHER, LAT0

def ls(page, key): return json.loads(page.evaluate(f"localStorage.getItem('kobd_{key}') || 'null'"))
def wait(page, expr, t=20000): page.wait_for_function(expr, timeout=t)
def connect(page):
    page.click("#btnConnect"); wait(page, "document.getElementById('status').textContent.includes('Connected')")

with app(gps={"permission": "prompt", "promptAnswer": "allow"}, net={"overpass": overpass_fixture(), "weather": WEATHER}) as page:
    g = lambda e: page.evaluate("__mock.gps." + e)
    page.wait_for_timeout(600)
    check(g("watches.length") == 0 and g("polls.length") == 0 and g("prompts") == 0, "GPS is idle before connecting: no watch, no prompt")
    page.evaluate("__mock.cruise = 44; __mock.gps.speed = 12")              # OBD 44 km/h vs GPS 12 m/s = 43.2 km/h -> about +1.9 %
    connect(page)
    wait(page, "__mock.gps.watches.length >= 1")
    check(g("prompts") == 1, "permission asked exactly once")
    check(g("watches[0].high") is True, "moving: high-accuracy watch")
    wait(page, "G.state === 'ok'", 8000)
    loc = ls(page, "loc")
    check(loc and abs(loc["lat"] - LAT0) < 0.01, f"position cached for the sunrise/sunset theme: {loc}")
    # --- phase 1: 30 mph road ---
    wait(page, "document.querySelector('#limit .rnd').textContent === '30'", 15000)
    check("OSM limit (may be wrong)" in page.inner_text("#limit"), "roundel is labelled 'OSM limit (may be wrong)'")
    check(page.is_visible("#limit"), "roundel visible next to the speed")
    page.screenshot(path=str(OUT / "gps-limit30.png"))
    # --- phase 2: 60 mph road, 30 m/s (67 mph: over) + the hill ---
    wait(page, "__mock.gps.dist >= 140")
    page.evaluate("__mock.cruise = 110; __mock.gps.speed = 30")
    wait(page, "document.querySelector('#limit .rnd').textContent === '60'", 12000)
    check(True, "limit changed 30 -> 60 as the road changed")
    wait(page, "__mock.gps.dist >= 330")
    grade = page.evaluate("tg.grade")
    check(grade is not None and 3.5 <= grade <= 8.5, f"smoothed gradient on the 6 % hill: {grade:.1f} %")
    page.click('nav button[data-p="car"]'); page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "gps-car.png"))
    gt = page.inner_text("#t_grade .val").split()[0]
    check(gt.replace(".", "").replace("-", "").isdigit(), f"gradient tile shows a number on the Car tab: {gt}")
    wait(page, "__mock.gps.dist >= 450")
    # --- GPS drops out mid-trip: OBD carries on, nothing breaks, the jump is not integrated ---
    km_before = page.evaluate("tg.km")
    page.evaluate("__mock.gps.dropout = true")
    wait(page, "G.state === 'lost'", 16000)
    check("GPS signal lost" in page.inner_text("#gpsInfo"), "dropout: quiet 'GPS signal lost' note")
    sp = page.inner_text("#t_gspd .val").strip()
    check(page.inner_text("#status").strip().startswith("Connected"), "dropout: OBD still connected")
    page.click('nav button[data-p="drive"]'); page.wait_for_timeout(400)
    check(page.inner_text("#t_speed .val").split()[0].isdigit(), "dropout: Drive speed still live from OBD")
    check(not page.errors, "dropout: no JS errors " + "; ".join(page.errors))
    page.screenshot(path=str(OUT / "gps-dropout.png"))
    page.evaluate("__mock.gps.dropout = false")
    wait(page, "G.state === 'ok'", 6000)
    km_after = page.evaluate("tg.km")
    check(km_after - km_before < 0.2, f"gap after the dropout not integrated as distance (+{(km_after-km_before)*1000:.0f} m while the car moved ~400 m unseen)")
    page.wait_for_timeout(3000)
    # --- summary numbers ---
    err = page.evaluate("(tg.spdObd/tg.spdGps - 1)*100")
    check(1.0 <= err <= 3.5, f"OBD vs GPS speed error {err:+.1f} % (true value about +1.9 %)")
    over = page.evaluate("tg.overS/tg.limS*100")
    check(15 <= over <= 90, f"% of time over the OSM limit: {over:.0f} % (30 mph zone under, 60 mph zone over)")
    check(9 <= page.evaluate("tg.ascent") <= 24, f"ascent ~18 m: {page.evaluate('tg.ascent'):.0f} m")
    page.click('nav button[data-p="style"]'); page.wait_for_timeout(500)
    ot = " ".join(page.inner_text("#t_over .val").split())
    check("% of time" in ot and "OSM" in page.inner_text("#t_over .lab"), f"Style tab shows % over limit, labelled OSM/may be wrong: '{ot}'")
    page.screenshot(path=str(OUT / "gps-style.png"))
    page.click('nav button[data-p="car"]'); page.wait_for_timeout(300)
    check("Weather at trip start: 8 °C, wind 14 mph, rain" in page.inner_text("#gpsInfo"), "weather shown: " + page.inner_text("#gpsInfo").split("\n")[1])
    # --- trip saved with route + features ---
    page.evaluate("endTrip('test')")
    t = ls(page, "trips")[-1]
    check(3 <= len(t["route"]) <= 150 and abs(t["route"][0][0] - LAT0) < 0.003, f"simplified route stored with the trip ({len(t['route'])} points: start, the bend, the end)")
    check(t["ascent"] >= 9 and t["spdErr"] is not None and t["overPct"] is not None and t["gpsKm"] > 0.3, f"trip has ascent {t['ascent']} m, speedo error {t['spdErr']} %, over {t['overPct']} %")
    check(t["wx"]["temp"] == 7.5 and t["wx"]["rain"] == 1, "weather stored with the trip")
    f = t["feat"]
    check(f["climb"] > 0.5 and f["wind"] == 14 and f["rain"] == 1, f"model features: climb {f['climb']:.1f} %, wind {f['wind']} mph, rain {f['rain']}")
    # --- privacy + caching of the look-ups ---
    wx = [r for r in page.net["log"] if "open-meteo" in r["url"]]
    ov = [r for r in page.net["log"] if "overpass" in r["url"]]
    check(len(wx) == 1 and "latitude=51.45&longitude=-2.59" in wx[0]["url"], "weather asked once, position rounded to 2 decimals: " + wx[0]["url"].split("?")[1][:40])
    boxes = [r["body"] for r in ov]
    check(len(boxes) == len(set(boxes)) and any("51.44,-2.61,51.46,-2.58" in b.replace("%2C", ",") for b in boxes), f"speed limits asked per map tile, never the same tile twice ({len(ov)} tiles: the one we were on + neighbours we drove towards)")
    blob = json.dumps(page.net["log"])
    check("51.4545" not in blob and "2.5879" not in blob, "no exact position ever sent to the look-up services")
    page.click("#btnStop"); page.wait_for_timeout(400)
    check(g("active()") == 0, "GPS watch cleared on Stop (battery)")
    check(not page.errors, "no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))

    # --- offline: cached tile + cached weather still work; with nothing cached it is simply 'no data' ---
    page.net["offline"] = True; n0 = len(page.net["log"])
    page.reload(); page.wait_for_timeout(500)
    page.evaluate("__mock.cruise = 44; __mock.gps.speed = 12; __mock.gps.permission = 'granted'"); connect(page)   # a real browser remembers the grant across reloads
    wait(page, "document.querySelector('#limit .rnd').textContent === '30'", 15000)
    check(len([r for r in page.net["log"][n0:] if "overpass" in r["url"]]) == 0, "offline: speed limit comes from the on-device cache (no request made)")
    wait(page, "tg.wx != null", 15000); page.click('nav button[data-p="car"]'); page.wait_for_timeout(400)
    check("Weather at trip start: 8 °C" in page.inner_text("#gpsInfo"), "offline: cached weather used")
    page.click("#btnStop"); page.wait_for_timeout(300)
    page.evaluate("Object.keys(localStorage).filter(k => k.startsWith('kobd_osm') || k === 'kobd_wx').forEach(k => localStorage.removeItem(k))")
    page.reload(); page.wait_for_timeout(500)
    page.evaluate("__mock.cruise = 44; __mock.gps.speed = 12; __mock.gps.permission = 'granted'"); connect(page)   # a real browser remembers the grant across reloads
    wait(page, "G.state === 'ok'", 8000); page.wait_for_timeout(4000)
    check(not page.is_visible("#limit"), "offline + nothing cached: no roundel, no fuss")
    page.click('nav button[data-p="car"]'); page.wait_for_timeout(400)
    check("no data" in page.inner_text("#gpsInfo"), "weather says 'no data' quietly")
    check(page.inner_text("#t_gspd .val").split()[0].isdigit(), "GPS speed itself still works offline")
    check(page.inner_text("#status").strip().startswith("Connected") and not page.errors, "OBD connected, no errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))
    page.screenshot(path=str(OUT / "gps-offline.png"))
