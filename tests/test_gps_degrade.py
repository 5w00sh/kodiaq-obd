"""Test 8: GPS degrades gracefully. No GPS at all, blocked, dismissed, approximate-only (Wi-Fi tablet), battery duty cycle,
foreground only. OBD must work in every case and nothing may nag or throw."""
import json
from common import app, check, OUT, overpass_fixture, WEATHER

NET = {"overpass": overpass_fixture(), "weather": WEATHER}
def ls(page, key): return json.loads(page.evaluate(f"localStorage.getItem('kobd_{key}') || 'null'"))
def wait(page, expr, t=20000): page.wait_for_function(expr, timeout=t)
def connect(page):
    page.click("#btnConnect"); wait(page, "document.getElementById('status').textContent.includes('Connected')")
def obd_ok(page, label):
    page.wait_for_timeout(2500)
    sp = page.inner_text("#t_speed .val").split()[0]
    check(sp.isdigit() and page.inner_text("#status").startswith("Connected") and not page.errors, f"{label}: OBD live ({sp} mph), no errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))
def car_text(page):
    page.click('nav button[data-p="car"]'); page.wait_for_timeout(400); return page.inner_text("#gpsInfo")

# 1. a tablet with no location hardware at all
with app(gps={"unsupported": True}, net=NET) as page:
    connect(page); obd_ok(page, "no GPS device")
    check("No GPS on this device" in car_text(page), "message: 'No GPS on this device ...'")
    check(not page.is_visible("#limit") and ls(page, "loc") is None, "no roundel, nothing stored")
    page.screenshot(path=str(OUT / "gps-none.png"))
    check(not any("overpass" in r["url"] or "open-meteo" in r["url"] for r in page.net["log"]), "no look-ups without a location")

# 2. permission already blocked
with app(gps={"permission": "denied"}, net=NET) as page:
    connect(page); obd_ok(page, "permission blocked")
    check("blocked" in car_text(page), "message explains how to allow it")
    check(page.evaluate("__mock.gps.watches.length") == 0 and page.evaluate("__mock.gps.prompts") == 0, "no watch, no prompt")

# 3. prompt dismissed: asked once, never nags again
with app(gps={"permission": "prompt", "promptAnswer": "dismiss"}, net=NET) as page:
    connect(page); obd_ok(page, "prompt dismissed")
    check(page.evaluate("__mock.gps.prompts") == 1, "asked once")
    page.click("#btnStop"); page.wait_for_timeout(300); connect(page); page.wait_for_timeout(1500)
    check(page.evaluate("__mock.gps.prompts") == 1, "second Connect does not ask again")
    check("blocked" in car_text(page), "tells you where to switch it on")
    page.click("#btnGps"); page.click("#btnGps"); page.wait_for_timeout(800)   # off, then on = the deliberate retry
    check(page.evaluate("__mock.gps.prompts") == 2, "the GPS switch in the Car tab is the way to ask again")
    check(not page.errors, "no JS errors")

# 4. Wi-Fi-only tablet: approximate location (800 m): weather + theme yes; speed/hills/limits no
with app(gps={"acc": 800}, net=NET) as page:
    page.evaluate("__mock.cruise = 44; __mock.gps.speed = 12")
    connect(page); wait(page, "G.state === 'coarse'", 10000); obd_ok(page, "approximate location")
    txt = car_text(page)
    check("Approximate location only" in txt and "weather" in txt, "message: approximate only")
    check(ls(page, "loc") is not None, "approximate position still keeps the day/night theme fresh")
    check("Weather at trip start: 8 °C" in txt, "weather still works on a coarse fix")
    check(not page.is_visible("#limit") and page.evaluate("tg.route.length") == 0 and page.evaluate("tg.km") == 0, "no limits, no route, no distance from a coarse fix")
    check(not any("overpass" in r["url"] for r in page.net["log"]), "no map look-ups")
    page.screenshot(path=str(OUT / "gps-coarse.png"))

# 5. battery: high accuracy only while moving; rest when stationary; stop clears everything
with app(gps={}, net=NET) as page:
    page.evaluate("GPS_IDLE_MS = 3000; __mock.cruise = 0; __mock.gps.speed = 0")
    connect(page)
    wait(page, "__mock.gps.watches.length >= 1")
    check(page.evaluate("__mock.gps.activeHigh()") == 1, "starts with one high-accuracy watch")
    wait(page, "G.mode === 'idle'", 15000)
    check(page.evaluate("__mock.gps.active()") == 0, "stationary: high-accuracy watch released")
    check(page.evaluate("__mock.gps.polls.length") >= 1 and page.evaluate("__mock.gps.polls.every(p => !p.high)"), "stationary: only an occasional low-accuracy look")
    check("resting" in car_text(page), "Car tab says GPS is resting")
    page.screenshot(path=str(OUT / "gps-resting.png"))
    page.evaluate("__mock.cruise = 50; __mock.gps.speed = 14")
    wait(page, "G.mode === 'high' && __mock.gps.activeHigh() === 1", 10000)
    check(True, "moving again: high-accuracy watch back within a few seconds")
    # foreground only: page hidden -> GPS off, visible -> back
    page.evaluate("Object.defineProperty(document, 'visibilityState', {value:'hidden', configurable:true}); document.dispatchEvent(new Event('visibilitychange'))")
    check(page.evaluate("__mock.gps.active()") == 0, "page hidden: GPS released (foreground only)")
    page.evaluate("Object.defineProperty(document, 'visibilityState', {value:'visible', configurable:true}); document.dispatchEvent(new Event('visibilitychange'))")
    check(page.evaluate("__mock.gps.active()") == 1, "page visible again: GPS resumes")
    page.click("#btnStop"); page.wait_for_timeout(300)
    check(page.evaluate("__mock.gps.active()") == 0 and page.evaluate("G.timer") is None and page.evaluate("G.active") is False, "Stop: watch cleared, timers cleared")
    check(not page.errors, "no JS errors")

# 6. Demo mode also uses GPS (and stops with it)
with app(gps={}, net=NET) as page:
    page.click("#btnDemo"); page.wait_for_timeout(1500)
    check(page.evaluate("__mock.gps.active()") == 1, "Demo starts GPS")
    page.click("#btnStop"); page.wait_for_timeout(300)
    check(page.evaluate("__mock.gps.active()") == 0, "Stop ends it")

# 7. GPS switched off in settings: OBD only
with app(gps={}, net=NET) as page:
    page.evaluate("localStorage.setItem('kobd_gpsOn', 'false')"); page.reload(); page.wait_for_timeout(400)
    connect(page); obd_ok(page, "GPS switched off")
    check(page.evaluate("__mock.gps.watches.length") == 0, "GPS off: never starts")
    check("GPS is off" in car_text(page), "Car tab: 'GPS is off'")
