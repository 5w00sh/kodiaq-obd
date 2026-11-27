"""Test 19 (v6.1.6): trip map from the Style tab. Vendored Leaflet (no CDN), OSM tiles online with attribution, route-outline fallback offline, Speed / Roughness layers
(roughness labelled 'uncalibrated – speed bumps not excluded'), tap a point for time/speed/raw values, fits and stays readable at 360x760 and 412x915, mocked rows."""
import json, math
from common import app, check, OUT

def wait(page, expr, t=20000): page.wait_for_function(expr, timeout=t)
ID = 1700000000000
def make_rows():
    rows = []
    for i in range(120):
        f = i / 119; lat = 51.45 + f * 0.03; lon = -2.60 + 0.02 * math.sin(f * 3.0) + f * 0.02
        rough = 0.25 + (1.2 if 50 <= i < 70 else 0) + 0.05 * math.sin(i)           # a rough stretch in the middle
        rows.append({"t": ID + i * 1000, "lat": round(lat, 6), "lon": round(lon, 6), "acc": 8, "speed": round(20 + 80 * math.sin(f * math.pi), 1), "rpm": 1500 + i * 5, "n": 50,
                     "vRms": round(rough, 3), "vPp": round(rough * 3, 3), "jerkMax": round(rough * 20, 2), "rollRms": 3.0, "pitchRms": 2.0, "yawRms": 1.0, "gx": 1.0, "gy": 0.0, "gz": 9.81})
    return rows
TRIP = {"date": "2026-11-20T08:00:00.000Z", "miles": 3.4, "litres": 0.3, "mpg": 45.0, "per10": 1, "score": 80, "rr": ID, "route": [[51.45, -2.6], [51.47, -2.58], [51.48, -2.56]]}
TRIP_NOREC = {"date": "2026-11-19T08:00:00.000Z", "miles": 2.0, "litres": 0.2, "mpg": 44.0, "per10": 1, "score": 80, "route": [[51.45, -2.6], [51.46, -2.59], [51.47, -2.57]]}
TRIP_NOGPS = {"date": "2026-11-18T08:00:00.000Z", "miles": 1.0, "litres": 0.1, "mpg": 44.0, "per10": 1, "score": 80}

JS_FIT = """() => {
  const bad = [], mv = document.getElementById('mapView').getBoundingClientRect(), main = document.querySelector('main').getBoundingClientRect();
  if (mv.left < main.left - 1 || mv.right > main.right + 1 || mv.bottom > main.bottom + 1 || mv.top < main.top - 1) bad.push('map view outside the tab area');
  if (document.scrollingElement.scrollWidth > innerWidth + 1 || document.scrollingElement.scrollHeight > innerHeight + 1) bad.push('page scrolls');
  const box = document.getElementById('mapBox').getBoundingClientRect(); if (box.height < 200 || box.width < 300) bad.push('map too small ' + Math.round(box.width) + 'x' + Math.round(box.height));
  for (const id of ['mapClose', 'mapSpeed', 'mapRough']) { const r = document.getElementById(id).getBoundingClientRect(); if (r.width < 40 || r.height < 36 || r.right > mv.right + 1 || r.bottom > box.top + 1) bad.push(id + ' unusable ' + Math.round(r.width) + 'x' + Math.round(r.height)); }
  const t = document.getElementById('mapTitle'); if (t.scrollWidth > t.clientWidth + 1 && getComputedStyle(t).textOverflow !== 'ellipsis') bad.push('title clipped');
  for (const sel of ['#mapLegend', '#mapLegend .ends span', '#mapLegend .cap', '#mapInfo']) for (const e of document.querySelectorAll(sel)) { if (!e.getClientRects().length) continue;
    if (parseFloat(getComputedStyle(e).fontSize) < 12) bad.push(sel + ' font < 12px'); const r = e.getBoundingClientRect(); if (r.right > mv.right + 1 || r.bottom > mv.bottom + 1) bad.push(sel + ' off screen'); }
  const leg = document.getElementById('mapLegend'), inf = document.getElementById('mapInfo'); if (leg.scrollWidth > leg.clientWidth + 1 || inf.scrollWidth > inf.clientWidth + 1) bad.push('legend/info clipped sideways');
  const at = document.querySelector('.leaflet-control-attribution'); if (at) { const r = at.getBoundingClientRect(); if (r.right > mv.right + 1 || r.bottom > box.bottom + 1) bad.push('attribution off the map'); }
  return bad;
}"""

for theme in ("night", "day"):
    for w, h in ((360, 760), (412, 915)):
        with app(viewport=(w, h), mock=False, theme=theme, net={"tiles": True}) as page:
            page.evaluate("([t1, t2, t3]) => { store.set('trips', [t3, t2, t1]); tripsCache = store.get('trips', []); renderLearned(); }", [TRIP, TRIP_NOREC, TRIP_NOGPS][::-1] if False else [TRIP, TRIP_NOREC, TRIP_NOGPS])
            page.evaluate("([id, rows]) => RR.put(id, rows[0].t, rows)", [ID, make_rows()])
            page.click('nav button[data-p="style"]'); page.wait_for_timeout(400)
            tag = f"{theme} {w}x{h}"
            check(page.locator("#trips .trip").count() == 3 and "Tap a trip" in page.inner_text("#tripsHint"), f"{tag}: trips are tappable rows ({page.locator('#trips .trip').count()})")
            check(page.evaluate("typeof L") == "undefined", f"{tag}: the map library is not loaded until a map is opened")
            page.locator('#trips .trip[data-d="2026-11-20T08:00:00.000Z"]').click(); wait(page, "window.L && MapUI.map && document.querySelectorAll('.leaflet-tile-loaded').length > 0")
            check(page.evaluate("document.querySelector('script[src=\"vendor/leaflet.js\"]') !== null") and not any("unpkg" in r["url"] or "cdn" in r["url"] for r in page.net["log"]), f"{tag}: Leaflet comes from vendor/ (no CDN request)")
            page.wait_for_timeout(600)
            bad = page.evaluate(JS_FIT); check(not bad, f"{tag}: map view fits, readable (speed layer)" + ("" if not bad else ": " + "; ".join(bad)))
            check("OpenStreetMap" in page.inner_text(".leaflet-control-attribution") and page.locator(".leaflet-tile-loaded").count() > 0, f"{tag}: OSM tiles online, attribution shown")
            tiles_n = len(page.net["tiles_log"]); check(0 < tiles_n <= 30, f"{tag}: light tile use ({tiles_n} tiles for the whole trip view)")
            sp = page.evaluate("window.__mapLayers"); check(len(sp) >= 6 and len(set(sp)) >= 6, f"{tag}: route coloured by speed ({len(set(sp))} colours)")
            check("mph" in page.inner_text("#mapLegend") and "uncalibrated" not in page.inner_text("#mapLegend"), f"{tag}: speed legend: {' '.join(page.inner_text('#mapLegend').split())}")
            if (w, h) == (360, 760) and theme == "night": page.screenshot(path=str(OUT / "map-speed-360x760.png"))
            # roughness layer
            page.click("#mapRough"); page.wait_for_timeout(400)
            ro = page.evaluate("window.__mapLayers")
            check("uncalibrated – speed bumps not excluded" in page.inner_text("#mapLegend") and page.is_visible("#mapLegend .cap"), f"{tag}: roughness caption: uncalibrated – speed bumps not excluded")
            check(sorted(set(ro)) != sorted(set(sp)) and any(c.lower() in ("#a50026", "#c43c26", "#e5532d") or int(c[1:3], 16) > 150 for c in ro) and any(int(c[3:5], 16) > 140 and int(c[1:3], 16) < 120 for c in ro), f"{tag}: roughness colours differ (green to red)")
            bad = page.evaluate(JS_FIT); check(not bad, f"{tag}: roughness layer fits, readable (caption included)" + ("" if not bad else ": " + "; ".join(bad)))
            if (w, h) == (412, 915) and theme == "day": page.screenshot(path=str(OUT / "map-roughness-412x915.png"))
            # tap a point: the rough stretch around row 60
            pos = page.evaluate("(() => { const p = MapUI.map.latLngToContainerPoint([51.45 + 0.03 * 60 / 119, -2.60 + 0.02 * Math.sin(60 / 119 * 3.0) + 60 / 119 * 0.02]), b = document.getElementById('mapBox').getBoundingClientRect(); return {x: b.left + p.x, y: b.top + p.y}; })()")
            page.mouse.click(pos["x"], pos["y"]); page.wait_for_timeout(400)
            tp = page.evaluate("window.__mapTap"); info = page.inner_text("#mapInfo")
            check(tp is not None and abs(tp["t"] - (ID + 60000)) <= 2000 and "mph" in info and "accel RMS" in info and "rpm" in info and ":" in info, f"{tag}: tap shows time, speed and raw values: {info}")
            bad = page.evaluate(JS_FIT); check(not bad, f"{tag}: still fits with the info line" + ("" if not bad else ": " + "; ".join(bad)))
            page.click("#mapSpeed"); page.wait_for_timeout(300); check(page.evaluate("window.__mapLayers") == sp, f"{tag}: back to the speed layer")
            page.click("#mapClose"); page.wait_for_timeout(300)
            check(not page.is_visible("#mapView") and page.is_visible("#trips"), f"{tag}: Close returns to the Style tab")
            # a trip without recorded rows: outline only
            page.locator('#trips .trip[data-d="2026-11-19T08:00:00.000Z"]').click(); wait(page, "MapUI.map != null"); page.wait_for_timeout(500)
            check("route outline only" in page.inner_text("#mapLegend") and page.evaluate("window.__mapLayers.length") >= 1, f"{tag}: trip without road data: outline + how to record")
            bad = page.evaluate(JS_FIT); check(not bad, f"{tag}: outline view fits" + ("" if not bad else ": " + "; ".join(bad)))
            page.click("#mapClose")
            page.locator('#trips .trip[data-d="2026-11-18T08:00:00.000Z"]').click(); page.wait_for_timeout(500)
            check("no GPS route" in page.inner_text("#mapBox"), f"{tag}: a trip with no GPS says so")
            page.click('nav button[data-p="car"]'); page.wait_for_timeout(300)
            check(not page.is_visible("#mapView"), f"{tag}: switching tab closes the map")
            check(not page.errors, f"{tag}: no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))

# ---------- offline: tiles fail -> blank canvas with the route outline ----------
with app(viewport=(360, 760), mock=False, net={"tiles": False}) as page:
    page.evaluate("([t1]) => { store.set('trips', [t1]); tripsCache = store.get('trips', []); renderLearned(); }", [TRIP])
    page.evaluate("([id, rows]) => RR.put(id, rows[0].t, rows)", [ID, make_rows()])
    page.click('nav button[data-p="style"]'); page.wait_for_timeout(300); page.locator("#trips .trip").first.click()
    wait(page, "MapUI.offline === true", 25000)
    check("route outline only" in page.inner_text("#mapInfo") and page.evaluate("window.__mapLayers.length") >= 6 and page.locator(".leaflet-tile-loaded").count() == 0, "offline (tiles fail): blank map, route outline + speed colours still drawn, message shown")
    bad = page.evaluate(JS_FIT); check(not bad, "offline view fits" + ("" if not bad else ": " + "; ".join(bad)))
    page.screenshot(path=str(OUT / "map-offline-360x760.png"))
    page.click("#mapRough"); page.wait_for_timeout(300); check("uncalibrated" in page.inner_text("#mapLegend"), "offline: roughness layer + caption still work")
    check(not page.errors, "offline: no JS errors")
