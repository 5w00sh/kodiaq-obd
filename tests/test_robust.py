"""Test 13 (v6.0.5, items 5-8): bogus temperatures (0xFF / > 150 C) never shown or learned, short stops merge into one trip, demo samples never reach the CSV,
cranking-dip voltage is kept apart from battery readings."""
import json
from common import app, check, OUT

def ls(page, key): return json.loads(page.evaluate(f"localStorage.getItem('kobd_{key}') || 'null'"))
def wait(page, expr, t=25000): page.wait_for_function(expr, timeout=t)
def connect(page):
    page.click("#btnConnect"); wait(page, "document.getElementById('status').textContent.includes('Connected')")
def txt(page, sel): return " ".join(page.inner_text(sel).split())

# ---------- 5. bogus temperatures ----------
with app() as page:
    ev = page.evaluate
    check(ev("[tempC(255), tempC(40+151), tempC(40+150), tempC(0), tempC(null), tempC(128)]") == [None, None, 150, -40, None, 88], "tempC: 0xFF and > 150 C -> null, 150 C and -40 C are valid")
    check(ev("[PIDS.oil.f([255]), PIDS.coolant.f([255]), PIDS.iat.f([255]), PIDS.amb.f([255]), DEC['5C'][2]([255]), DEC['05'][2]([255]), DEC['0F'][2]([255]), DEC['46'][2]([255]), DEC['67'][2]([1,255,0]), DEC['77'][2]([3,255,0x59]), DEC['9B'][3]([0x3f,0x80,255,0x3a])]") == [None] * 10 + [None], "every temperature decoder returns null for raw 255")
    check(ev("[PIDS.oil.f([215+40]), DEC['5C'][2]([200])]") == [None, None], "oil 215 C (raw 255) and 160 C (raw 200) both rejected")
    ev("show('oil', 215)"); check(txt(page, "#t_oil .val").startswith("–") and "na" in ev("document.getElementById('t_oil').className"), "show() refuses 215 C: tile stays –")
    ev("show('coolant', 151); show('iat', 300); show('amb', -60)"); check(all(txt(page, f"#t_{n} .val").startswith("–") for n in ("coolant", "iat", "amb")), "coolant 151 / intake 300 / outside -60 all shown as –")
    ev("show('egt', 610)"); check(txt(page, "#t_egt .val").startswith("610"), "exhaust temps (legitimately > 150) are not touched")
    check(ev("learnValue('drive', '5C', 215)") is None and ev("pidStats['drive:5C']") is None, "learnValue refuses 215 C and creates no stats entry")
    check(ev("learnValue('drive', '5C', 88)") is None and ev("pidStats['drive:5C'].n") == 1, "...but still learns a normal 88 C")

with app() as page:                                         # through the mock: oil byte 0xFF for the first samples, then normal
    page.evaluate("__mock.oilRaw = 255"); connect(page); page.wait_for_timeout(4000)
    check(txt(page, "#t_oil .val").startswith("–") and page.evaluate("latest.oil == null"), f"oil raw 0xFF: tile {txt(page, '#t_oil .val')}, latest.oil null (was 215 °C)")
    check("5C no reply" not in page.inner_text("#log") and "oil marked unsupported" not in page.inner_text("#log"), "a not-ready sensor is not treated as 'unsupported'")
    page.click('nav button[data-p="car"]'); page.click("#btnScan"); wait(page, "!document.getElementById('btnScan').disabled", 60000)
    o = page.evaluate("scans[scans.length-1].sweep.out['5C']")
    check(o["ok"] and o["v"] is None and "not ready" in (o["extra"] or ""), f"scan: oil recorded as raw only, 'sensor not ready, ignored' ({o['raw']})")
    page.evaluate("learningCheck()"); page.wait_for_timeout(5000)
    check(page.evaluate("Object.keys(pidStats).filter(k => /^(off|idle|cold|drive):5C$/.test(k)).length") == 0, "pidStats has no learned oil value from not-ready samples")
    page.evaluate("__mock.oilRaw = 168"); page.wait_for_timeout(5000)
    check(txt(page, "#t_oil .val").startswith("128"), f"oil 0xA8 -> 128 °C shows once the sensor is ready ({txt(page, '#t_oil .val')})")
    page.evaluate("__mock.oilRaw = 255"); page.wait_for_timeout(5000)
    check(txt(page, "#t_oil .val").startswith("–"), "and back to – if it drops out again")
    check(not page.errors, "no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))

# ---------- 6. short stops merge ----------
with app() as page:
    page.evaluate("__mock.cruise = 90; TRIP_STOP_MS = 3000; TRIP_MERGE_MS = 9000"); connect(page)
    wait(page, "document.getElementById('status').textContent.includes('trip running')"); page.wait_for_timeout(14000)
    page.evaluate("__mock.engine = false"); wait(page, "document.getElementById('status').textContent.includes('trip paused')")
    check(not ls(page, "trips"), "engine off past the stop threshold: trip paused, nothing saved")
    page.wait_for_timeout(2000); page.evaluate("__mock.engine = true"); wait(page, "document.getElementById('status').textContent.includes('trip running')")
    log = page.inner_text("#log")
    check(log.count("→ new trip") == 1 and "same trip" in log and log.count("stop logged") == 1, "restart inside the window: same trip, one stop logged, one 'new trip'")
    check(page.evaluate("tripStops.length") == 1 and page.evaluate("tripStops[0].secs") is not None, f"stop recorded with its length ({page.evaluate('tripStops[0].secs')} s)")
    page.wait_for_timeout(6000); page.evaluate("__mock.engine = false")
    wait(page, "document.getElementById('status').textContent.includes('trip saved')", 40000)
    t = ls(page, "trips")
    check(len(t) == 1 and len(t[0]["stops"]) == 2 and t[0]["miles"] > 0.25, f"one trip saved with both legs ({t[0]['miles']:.2f} mi) and {len(t[0]['stops'])} stops")
    page.click('nav button[data-p="style"]'); page.wait_for_timeout(300)
    check("2 stops" in page.inner_text("#trips"), "Style tab trip list shows '2 stops'")
    check(not page.errors, "no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))

# ---------- 7. demo never touches the CSV ----------
with app() as page:
    page.click("#btnDemo"); page.wait_for_timeout(3500)
    check(page.evaluate("samples.length") == 0 and page.is_disabled("#btnCsv") and "not logged" in page.inner_text("#logInfo"), f"Demo logs no samples ({page.inner_text('#logInfo')})")
    page.click("#btnStop"); page.wait_for_timeout(400)
    check(page.evaluate("samples.length") == 0 and page.is_disabled("#btnCsv"), "after Demo stops: no samples, CSV button disabled")
    page.evaluate("samples.push({t:'2026-11-26T08:01:00.000Z', speed:60, demo:true}); samples.push({t:'2026-11-26T08:02:00.000Z', speed:61, demo:true})")   # a stray demo sample from an older build/session
    connect(page); page.wait_for_timeout(3500)
    n = page.evaluate("samples.length")
    check(page.evaluate("samples.every(s => !s.demo)"), f"real connection: any demo-tagged sample is purged ({n} samples now)")
    page.evaluate("__mock.engine = true"); page.wait_for_timeout(3500)
    check(page.evaluate("samples.length") > 0 and page.evaluate("samples.every(s => !s.demo)") and not page.is_disabled("#btnCsv"), "real drive logged, CSV available")
    page.click("#btnStop"); page.wait_for_timeout(400)
    n1 = page.evaluate("samples.length"); page.click("#btnDemo"); page.wait_for_timeout(2500); page.click("#btnStop"); page.wait_for_timeout(400)
    check(page.evaluate("samples.length") == n1 and not page.is_disabled("#btnCsv"), f"a Demo after a real drive leaves the real samples alone ({n1})")
    check(not page.errors, "no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))

# ---------- 8. cranking voltage ----------
with app() as page:
    ev = page.evaluate
    ev("latest.volt = 12.4; show('volt', 12.4); startAt = Date.now() - 3000")
    check(ev("handleVolt(10.0)") is False and ev("latest.volt") == 12.4 and txt(page, "#t_volt .val").startswith("12.4"), "10.0 V 3 s after start: not shown, latest.volt unchanged")
    check("crit" not in ev("document.getElementById('t_volt').className"), "...so no red low-battery tile")
    ev("handleVolt(9.7)"); cr = ev("crankLog"); check(len(cr) == 1 and abs(cr[0]["v"] - 9.7) < .01 and cr[0]["n"] == 2, f"logged separately as crank voltage, lowest dip kept ({cr[0]['v']} V over {cr[0]['n']} samples)")
    check(abs(ls(page, "crank")[0]["v"] - 9.7) < .01, "persisted in localStorage 'crank'")
    check("Crank voltage" in page.inner_text("#battInfo") and "9.7 V" in page.inner_text("#battInfo"), "shown on the Car tab's battery panel")
    ev("startAt = Date.now() - 11000")
    check(ev("handleVolt(13.3)") is True and ev("latest.volt") == 13.3 and len(ev("crankLog")) == 1, "11 s after start: normal reading again, no new crank entry")
    ev("startAt = null"); check(ev("handleVolt(13.2)") is True, "no start seen (connected with the engine running): everything is a normal reading")
    ev("latest.volt = 12.4; latest.rpm = 0; voltSkips = 0; show('volt', 12.4)")
    check(ev("[handleVolt(8.9), handleVolt(8.9), handleVolt(8.9)]") == [False, False, True] and ev("latest.volt") == 8.9, "a dip read just BEFORE the rpm rise (engine still off, > 1.5 V under the last reading) is ignored; after 2 in a row a real change shows")
    ev("latest.volt = 12.4; voltSkips = 0; show('volt', 12.4)"); check(ev("handleVolt(12.0)") is True, "a normal 0.4 V sag is a normal reading")
    connect(page); page.wait_for_timeout(1500); ev("pidStats = {}")
    s = ev("(async () => { startAt = Date.now() - 2000; const r = await sweep(); return r.out; })()")
    check(s["BATT"]["v"] is None and "cranking dip" in s["BATT"]["extra"] and s["42"]["v"] is None, f"sweep in the dip: battery + module voltage ignored ({s['BATT']['extra']})")
    check(not any(__import__("re").match(r"^(off|idle|cold|drive):(BATT|42)$", k) for k in ev("Object.keys(pidStats)")), "...and never learned")

with app() as page:                                      # end to end through the loop: start the engine with a 10.0 V dip
    page.evaluate("__mock.engine = false"); connect(page); page.wait_for_timeout(2500)
    pre = txt(page, "#t_volt .val")
    page.evaluate("__mock.crankUntil = Date.now() + 8000; __mock.engine = true")
    wait(page, "startAt != null", 15000); check(True, "engine start detected from the rpm rise")
    wait(page, "crankLog.length > 0", 20000)
    cr = page.evaluate("crankLog[0].v"); check(abs(cr - 10.0) < .11, f"cranking dip logged as crank voltage ({cr} V)")
    check("10.0" not in txt(page, "#t_volt .val"), f"battery tile did not show the dip ({txt(page, '#t_volt .val')})")
    page.wait_for_timeout(14000)
    v = txt(page, "#t_volt .val"); check(v.startswith("13."), f"after the window the tile shows the charging voltage ({v})")
    check(not any(k.endswith(":BATT") and "mean" in s and s["mean"] < 11 for k, s in page.evaluate("pidStats").items()), "no learned battery value from the dip")
    page.screenshot(path=str(OUT / "robust-battery.png")); page.click('nav button[data-p="car"]'); page.wait_for_timeout(400); page.screenshot(path=str(OUT / "robust-car-battery.png"))
    check(not page.errors, "no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))
