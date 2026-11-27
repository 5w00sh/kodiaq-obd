"""Test 16 (v6.1.3): the pre-start battery reading must not capture the cranking dip. Several ATRV reads over ~5 s (median), accepted only if rpm stays < 300 for 10 s
AFTER the reading; if the engine starts first the reading becomes crank voltage. 'Hold off starting for 10 s for a battery reading' while measuring. Real timers (~16 s per case)."""
import json
from common import app, check, OUT

def ls(page, key): return json.loads(page.evaluate(f"localStorage.getItem('kobd_{key}') || 'null'"))
def wait(page, expr, t=40000): page.wait_for_function(expr, timeout=t)
def connect(page):
    page.click("#btnConnect"); wait(page, "document.getElementById('status').textContent.includes('Connected')")
HOLD = "Hold off starting for 10 s for a battery reading"

# ---- A. engine stays off: median of several reads (one outlier dip ignored), accepted after 10 s ----
with app() as page:
    page.evaluate("__mock.engine = false"); connect(page)
    check(HOLD in page.inner_text("#status"), "A: status says: " + HOLD)
    page.evaluate("(() => { const seq = [12.5, 9.8, 12.5, 12.6, 12.5, 12.4, 12.5, 12.5]; let i = 0; window.__t = setInterval(() => { __mock.restVolt = seq[i++ % seq.length]; }, 700); })()")
    page.wait_for_timeout(5000)
    check(not ls(page, "batt"), "A: nothing recorded while still measuring / holding")
    wait(page, "JSON.parse(localStorage.getItem('kobd_batt')||'[]').length > 0", 40000)
    page.evaluate("clearInterval(window.__t)")
    b = ls(page, "batt"); log = page.inner_text("#log")
    check(len(b) == 1 and abs(b[0]["v"] - 12.5) < .11, f"A: median of the reads recorded ({b[0]['v']} V), the 9.8 V outlier ignored")
    check("median of" in log and "Battery before start" in log, "A: log says how it was measured")
    check(HOLD not in page.inner_text("#status") and not ls(page, "crank"), "A: message cleared, no crank entry")
    check(not page.errors, "A: no JS errors")

# ---- B. Start pressed right after Connect: the dip is crank voltage, NOT 'battery before start' ----
with app() as page:
    page.evaluate("__mock.engine = false"); connect(page); page.wait_for_timeout(1800)
    check(HOLD in page.inner_text("#status"), "B: measuring when Start is pressed")
    page.evaluate("__mock.crankUntil = Date.now() + 3500; __mock.engine = true")
    wait(page, "document.getElementById('log').textContent.includes('within 10 s of the battery reading')", 20000)
    page.wait_for_timeout(1500)
    check(not ls(page, "batt"), "B: NO 'battery before start' reading was recorded")
    cr = ls(page, "crank")
    check(cr and abs(cr[-1]["v"] - 10.0) < .11, f"B: the 10.0 V dip is kept as crank voltage ({cr[-1]['v'] if cr else None})")
    check("kept as crank voltage" in page.inner_text("#log"), "B: log: kept as crank voltage, not a resting reading")
    check(HOLD not in page.inner_text("#status"), "B: message gone (trip running)")
    check(not page.errors, "B: no JS errors")

# ---- C. Start pressed AFTER the 5 s of reads but inside the 10 s hold: still not accepted ----
with app() as page:
    page.evaluate("__mock.engine = false"); connect(page); page.wait_for_timeout(9000)
    check(not ls(page, "batt") and HOLD in page.inner_text("#status"), "C: 9 s in: still holding, nothing recorded yet")
    page.evaluate("__mock.engine = true")
    wait(page, "document.getElementById('log').textContent.includes('within 10 s of the battery reading')", 20000)
    check(not ls(page, "batt"), "C: engine started inside the 10 s hold: reading NOT accepted as a resting battery value")
    check("no resting reading kept" in page.inner_text("#log"), "C: log: no resting reading kept (rest voltage 12.4 V is not a dip)")

# ---- D. engine already running at connect: no measurement, no message ----
with app() as page:
    connect(page); page.wait_for_timeout(1500)
    check(HOLD not in page.inner_text("#status") and not ls(page, "batt") and "pre-start check skipped" in page.inner_text("#log"), "D: engine already running: no hold message, no reading")

# ---- E. Stop while measuring leaves nothing behind ----
with app() as page:
    page.evaluate("__mock.engine = false"); connect(page); page.wait_for_timeout(2000); page.click("#btnStop"); page.wait_for_timeout(500)
    check(page.evaluate("pre") is None and HOLD not in page.inner_text("#status") and not ls(page, "batt"), "E: Stop during the measurement: no reading, message gone")
