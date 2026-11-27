"""Test 12 (v6.0.5): multi-frame (ISO-TP) mode-01 replies, two ECUs, experimental decoders, coolant warning rule, battery-reading message.
Regression for the first real health scan: 69 70 71 78 7A 7F 83 85 88 8B 8C 8F 9C A7 all showed "no reply" because only single-line replies were parsed."""
import json
from common import app, check, OUT

LONG = {"69": 7, "70": 10, "71": 6, "78": 9, "7A": 7, "7F": 13, "83": 5, "85": 10, "88": 13, "8B": 7, "8C": 16, "8F": 5, "9C": 9, "A7": 8}
def wait(page, expr, t=25000): page.wait_for_function(expr, timeout=t)
def num(page, sel):
    import re
    m = re.match(r"-?[\d.]+", " ".join(page.inner_text(sel).split())); return m.group(0) if m else "–"
def connect(page):
    page.click("#btnConnect"); wait(page, "document.getElementById('status').textContent.includes('Connected')")

# ---------- parser unit checks (real ELM327 layouts) ----------
with app() as page:
    r = lambda lines, pid: page.evaluate("([l, p]) => { const r = pidReply(l, p); return r && r.bytes; }", [lines, pid])
    check(r(["00B", "0:41 8B 01 00 A0 00 1E", "1:00 0F"], "8B") == [1, 0, 0xA0, 0, 0x1E, 0, 0x0F], "one ECU, multi-frame with spaces (ATS1)")
    check(r(["00B", "0:418B0100A0001E", "1:000F"], "8B") == [1, 0, 0xA0, 0, 0x1E, 0, 0x0F], "one ECU, multi-frame without spaces (ATS0)")
    check(r(["009", "0:41780F0C80", "1:0CB30CE6", "2:0D19", "009", "0:417800EEEE", "1:EEEEEEEE", "2:EEEE"], "78") == [0x0F, 0x0C, 0x80, 0x0C, 0xB3, 0x0C, 0xE6, 0x0D, 0x19], "two ECUs, both multi-frame: the engine ECU (first) wins")
    check(r(["410D3C", "4100981B8013", "NO DATA"], "0D") == [0x3C], "single-frame reply still works, other lines ignored")
    check(r(["4100981B8013", "009", "0:41 8B 01 00 A0 00 1E", "1:00 0F"], "8B") == [1, 0, 0xA0, 0, 0x1E, 0, 0x0F], "single-frame line from another ECU before the multi-frame one")
    check(r(["NO DATA"], "8B") is None and r(["410D3C"], "0C") is None, "no matching message -> null")
    check(r(["4B01A", "0:416B", "1:", ":"], "6B") is None, "garbage lines do not throw")

# ---------- through the mock adapter: every long PID answers ----------
with app() as page:
    connect(page); page.wait_for_timeout(1500)
    for pid, n in LONG.items():
        b = page.evaluate(f"rawPid('{pid}')")
        check(b is not None and len(b) == n and 0xEE not in b, f"01{pid}: multi-frame, two-ECU reply parsed, {n} data bytes" + ("" if b and len(b) == n else f" (got {b})"))
    # DPF status / EGT / dP now decode
    page.evaluate("__mock.dpfTrigPct = 80; __mock.egtC = 310"); page.wait_for_timeout(4500)
    check(abs(page.evaluate("dpf.trigger") - 80) < 1 and num(page, "#t_dpf .val") == "80", f"DPF regen trigger from PID 8B: tile {num(page, '#t_dpf .val')}%")
    check(abs(page.evaluate("dpf.egt") - 325) < 1 and num(page, "#t_egt .val") == "325", f"EGT from PID 78 (max of 4 sensors): tile {num(page, '#t_egt .val')} °C")
    page.evaluate("__mock.dpfRegen = true"); page.wait_for_timeout(4500)
    check(page.evaluate("dpf.active"), "regen-active bit from PID 8B")
    page.evaluate("__mock.dpfRegen = false")
    check(abs(page.evaluate("decodeDp = DEC['7A'][2]([1,1,0xC2])") - 4.5) < .01, "DPF differential pressure from PID 7A: 4.5 kPa")
    # ---------- full health scan ----------
    page.click('nav button[data-p="car"]'); page.click("#btnScan"); wait(page, "!document.getElementById('btnScan').disabled", 60000)
    out = page.evaluate("scans[scans.length-1].sweep.out")
    missing = [k for k in LONG if not out[k]["ok"]]
    check(not missing, f"health scan: no 'no reply' on any long PID{'' if not missing else ': ' + ' '.join(missing)}")
    check(page.inner_text("#scanOut").count("no reply") == 0, "scan summary text has no 'no reply' anywhere")
    allRep = page.evaluate("[...supportedPids].filter(p => !['00','20','40','60','80','A0','C0'].includes(p) && !scans[scans.length-1].sweep.out[p].ok)")
    check(not allRep, f"health scan: every supported PID answered (silent: {allRep})")
    # experimental decoders from the real raw values
    d = lambda k: out[k]
    check(abs(d("9B")["v"] - 58 * 100 / 255) < .01 and d("9B")["extra"] == "tank 4 °C" and "experimental" in d("9B")["label"], f"9B 3f 80 2c 3a: AdBlue {d('9B')['v']:.1f}%, {d('9B')['extra']}, label '{d('9B')['label']}'")
    check(d("A4")["v"] == 1 and "experimental" in d("A4")["label"], "A4 01 00 00 00: gear 1 (experimental)")
    check(d("77")["v"] == 42 and d("77")["extra"] == "sensor 2 49 °C", f"77 03 52 59 00 00: charge-air {d('77')['v']} °C, {d('77')['extra']}")
    check(d("67")["v"] == 71 and "experimental" in d("67")["label"], "67 01 6f 00: coolant sensor 71 °C")
    check(abs(d("A2")["v"] - 236 / 32) < .001 and d("A2")["unit"] == "mg", f"A2 00 ec: {d('A2')['v']} mg/stroke")
    check(num(page, "#t_adblue .val") == "23" and "experimental" in page.inner_text("#t_adblue .lab").lower(), f"Car tab AdBlue tile: {' '.join(page.inner_text('#t_adblue .val').split())}")
    page.screenshot(path=str(OUT / "isotp-car-tab.png"))
    rep = page.evaluate("reportText(scans[scans.length-1])")
    check("AdBlue (DEF) level (experimental)" in rep and "raw 3f 80 2c 3a" in rep, "report lists the experimental readings with their raw bytes")
    page.click('nav button[data-p="drive"]'); page.wait_for_timeout(800)
    # ---------- 4. engine already running ----------
    msg = "Connect before starting the engine for a battery reading"
    v = page.evaluate("scans[scans.length-1].verdict")
    st = page.evaluate("scans[scans.length-1].state"); check(st in ("cold", "idle", "drive"), f"scan ran with the engine on (state {st})")
    check(any(msg in x["txt"] for x in v), "summary says: " + msg)
    check(not any("Battery before start" in x["txt"] for x in v), "no fake 'battery before start' reading")
    check(not page.errors, "no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))

with app() as page:                       # engine OFF at connect: normal battery reading, no hint
    page.evaluate("__mock.engine = false"); connect(page); page.wait_for_timeout(1000)
    page.click('nav button[data-p="car"]'); page.click("#btnScan"); wait(page, "!document.getElementById('btnScan').disabled", 60000)
    v = page.evaluate("scans[scans.length-1].verdict")
    check(page.evaluate("scans[scans.length-1].state") == "off" and any("Battery before start" in x["txt"] for x in v) and not any("Connect before starting" in x["txt"] for x in v), "engine off: 'Battery before start' shown, no 'connect before starting' hint")
    check(not page.errors, "no JS errors")

# ---------- 2. coolant warning rule ----------
with app() as page:
    def coolant(c, runS, fastMi, state="drive", noRun=False):
        out = {"05": {"ok": True, "v": c}}
        if not noRun: out["1F"] = {"ok": True, "v": runS}
        page.evaluate(f"trip.fastKm = {fastMi} * KM_PER_MILE")
        v = page.evaluate("([out, state]) => verdict({state, monitors:null, codes:{stored:[],pending:[],permanent:[]}, sweep:{out, flags:[]}})", [out, state])
        return next(x for x in v if x["txt"].startswith("Coolant"))
    r = coolant(75, 8 * 60, 1.0); check(r["lvl"] == "ok" and "warming up" in r["txt"], f"75 C after 8 min, mostly idling: no alarm ({r['lvl']}: {r['txt']})")
    r = coolant(75, 20 * 60, 4.9); check(r["lvl"] == "ok", "75 C after 20 min but only 4.9 mi above 30 mph: no alarm")
    r = coolant(75, 14 * 60 + 59, 9.0); check(r["lvl"] == "ok", "75 C, 5+ mi, but 14:59 running: no alarm")
    r = coolant(75, 15 * 60, 5.0); check(r["lvl"] == "warn" and "thermostat" in r["txt"], f"75 C after 15 min and 5 mi above 30 mph: warns ({r['txt']})")
    r = coolant(79, 40 * 60, 20.0); check(r["lvl"] == "warn", "79 C after 40 min / 20 mi: warns")
    r = coolant(80, 40 * 60, 20.0); check(r["lvl"] == "ok" and "warming" not in r["txt"], "80 C: normal")
    r = coolant(90, 5 * 60, 0); check(r["lvl"] == "ok", "90 C: normal")
    r = coolant(108, 5 * 60, 0); check(r["lvl"] == "warn" and "hot" in r["txt"], "108 C: still warns 'hot' regardless of run time")
    page.evaluate("trip.t0 = Date.now() - 20 * 60000"); r = coolant(75, 0, 6.0, noRun=True); check(r["lvl"] == "warn", "no PID 1F: falls back to the trip clock")
    # fast-distance accounting in the trip (integrate() skips gaps > ~10 s, so step in 2 s slices)
    page.evaluate("trip = {km:0, L:0, idleL:0, t0:Date.now(), odo0:null}; lastInt = performance.now() - 2000; integrate(40, 0)")        # 40 km/h = 24.9 mph: not fast
    a = page.evaluate("trip.fastKm || 0")
    page.evaluate("for (let i = 0; i < 5; i++){ lastInt = performance.now() - 2000; integrate(80, 0); }")                            # 5 x 2 s at 80 km/h = 0.222 km
    b = page.evaluate("trip.fastKm")
    check(a == 0 and abs(b - 0.222) < .01, f"trip.fastKm counts only distance above 30 mph (0 at 40 km/h, {b:.3f} km after 10 s at 80 km/h)")
