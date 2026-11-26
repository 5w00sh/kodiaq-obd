"""Test 5: engine cycle. off -> connect -> on -> off 30s+ -> on. Takes ~1.5 min (the app's 30 s off-timer is real time)."""
import json
from common import app, check, OUT

def ls(page, key):
    return json.loads(page.evaluate(f"localStorage.getItem('kobd_{key}') || 'null'"))
def status(page): return page.inner_text("#status")

with app() as page:
    page.evaluate("__mock.engine = false; __mock.cruise = 90")
    page.click("#btnConnect")
    page.wait_for_function("document.getElementById('status').textContent.includes('Connected')", timeout=20000)
    page.wait_for_timeout(1500)
    batt = ls(page, "batt")
    check(batt and 12.3 <= batt[-1]["v"] <= 12.5, f"pre-start battery recorded before the engine started ({batt[-1]['v'] if batt else None} V)")
    page.wait_for_function("(() => { try { const s = JSON.parse(localStorage.getItem('kobd_scans')||'[]'); return s.length>0 } catch(e){return false} })()", timeout=90000)
    scans = ls(page, "scans")
    check(scans[-1]["auto"] is True, f"automatic health scan ran and saved ({len(scans[-1]['verdict'])} verdict lines)")
    page.screenshot(path=str(OUT / "cycle-1-scan.png"))

    page.evaluate("__mock.engine = true")
    page.wait_for_function("document.getElementById('status').textContent.includes('trip running')", timeout=20000)
    check(True, "engine on -> trip started")
    page.wait_for_timeout(22000)                       # 90 km/h x 22 s is about 0.5 km, above the 0.3 km save threshold
    page.screenshot(path=str(OUT / "cycle-2-driving.png"))

    page.evaluate("__mock.engine = false")
    page.wait_for_function("document.getElementById('status').textContent.includes('trip saved')", timeout=60000)
    trips = ls(page, "trips")
    check(trips and len(trips) == 1 and trips[0]["miles"] > 0.15, f"trip saved after engine off ({trips[0]['miles']:.2f} mi)" if trips else "trip saved after engine off")
    page.screenshot(path=str(OUT / "cycle-3-saved.png"))

    page.evaluate("__mock.engine = true")
    page.wait_for_function("document.getElementById('status').textContent.includes('trip running')", timeout=20000)
    log = page.inner_text("#log")
    check(log.count("Engine on → new trip") == 2, "restart opened a new trip (2 'new trip' log lines)")
    check(len(ls(page, "trips")) == 1, "the saved trip was not duplicated or lost on restart")
    page.screenshot(path=str(OUT / "cycle-4-restart.png"))
    page.click("#btnStop"); page.wait_for_timeout(300)
    check(not page.errors, "no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))
