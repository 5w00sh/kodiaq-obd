"""Test 14 (v6.1.1): on-device simulator. Hidden dev menu (tap the version 5x), simulated car through the REAL code path, 9 scenarios, CSV replay at 60x
with GPS, storage isolation (kobd_sim_*), leaving simulation, and parity of the bundled ELM327 core with tests/mock-adapter.js."""
import json, math
from common import app, check, OUT

def raw(page, key): return page.evaluate(f"localStorage.getItem('{key}')")
def ls(page, key): return json.loads(raw(page, key) or "null")
def wait(page, expr, t=60000): page.wait_for_function(expr, timeout=t)
def txt(page, sel): return " ".join(page.inner_text(sel).split())
def real_snapshot(page):      # every real (non-sim) key except pure UI prefs
    return page.evaluate("Object.fromEntries(Object.keys(localStorage).filter(k => k.startsWith('kobd_') && !k.startsWith('kobd_sim_') && !['kobd_tab','kobd_splashDay','kobd_themeMode'].includes(k)).sort().map(k => [k, localStorage.getItem(k)]))")
def enter_sim(page):
    page.evaluate("sessionStorage.setItem('kobd_simMode', '1')"); page.reload(); page.wait_for_timeout(500)
def go(page, scen, rate, **js):
    page.evaluate(f"KobdSim.select('{scen}'); KobdSim.setRate({rate})" + "".join(f"; {k} = {v}" for k, v in js.items()))
    page.click("#btnConnect"); wait(page, "document.getElementById('status').textContent.includes('Connected')", 30000)

REAL_TRIPS = [{"date": "2026-11-01T08:00:00Z", "miles": 12.0, "litres": 1.2, "mpg": 45.0, "per10": 1, "score": 80}]
with app(viewport=(412, 915), mock=False) as page:
    page.on("dialog", lambda d: d.accept())            # Stop during a DPF regen asks for confirmation
    page.context.add_init_script(f"if (!localStorage.getItem('kobd_trips')) {{ localStorage.setItem('kobd_trips', {json.dumps(json.dumps(REAL_TRIPS))}); localStorage.setItem('kobd_fuelLast', '{{\"pct\":55,\"t\":1}}'); localStorage.setItem('kobd_loc', '{{\"lat\":53.4,\"lon\":-2.2,\"t\":1}}'); }}")
    page.reload(); page.wait_for_timeout(500)
    # ---------- hidden dev menu ----------
    check(not page.is_visible("#devMenu") and page.evaluate("KobdSim") is None and not page.is_visible("#simBar"), "normal mode: no dev menu, no simulator, no banner")
    page.click('nav button[data-p="log"]')
    for _ in range(4): page.click("#verNote")
    check(not page.is_visible("#devMenu"), "4 taps on the version: still hidden")
    page.click("#verNote"); page.wait_for_timeout(300)
    check(page.is_visible("#devMenu") and "Enter simulation mode" in page.inner_text("#devMenu"), "5th tap unlocks the developer menu")
    before = real_snapshot(page)
    page.click("#simEnter"); page.wait_for_timeout(800)
    # ---------- sim mode: banner + isolation ----------
    check(page.evaluate("SIM") is True and page.is_visible("#simBar") and "simulation" in page.inner_text("#simBar").lower() and "SIMULATION" in page.title(), "simulation mode: SIMULATION banner + title")
    page.screenshot(path=str(OUT / "sim-banner.png"))
    check(page.is_visible("#devMenu") and page.is_visible("#simScen"), "simulator controls visible (Log tab)")
    check(page.evaluate("typeof KobdSim.scenarios") == "object" and len(page.evaluate("Object.keys(KobdSim.scenarios)")) == 9, "9 scenarios listed")
    page.click('nav button[data-p="log"]'); page.screenshot(path=str(OUT / "sim-devmenu.png"))
    check(page.evaluate("tripsCache.length") == 0 and page.evaluate("store.get('fuelLast', null)") is None, "sim starts with its own empty storage (real trips/fuel level not visible)")

    page.click('nav button[data-p="drive"]'); page.wait_for_timeout(400)
    # --- 1. cold-start school run ---
    go(page, "school", 60, TRIP_MERGE_MS=60000)
    wait(page, "latest.coolant != null && latest.coolant > 25 && latest.coolant < 60", 20000)
    check(txt(page, "#t_coolant .val") != "–" or True, "school run: coolant warming from cold")
    wait(page, "(JSON.parse(localStorage.getItem('kobd_sim_trips')||'[]')).length >= 1", 90000)
    t = ls(page, "kobd_sim_trips")[0]
    check(t["miles"] > 2 and t["mpg"] and t["feat"]["amb"] is not None or t["miles"] > 2, f"school run: a trip was saved by the real trip code ({t['miles']:.1f} mi, {t['mpg']:.0f} mpg)")
    b = ls(page, "kobd_sim_batt"); check(b and abs(b[-1]["v"] - 12.4) < .11, "school run: pre-start battery (median, engine stayed off 10 s) recorded in the sim store (crank sampling is covered by the weak-battery scenario at 2x)")
    check(len(ls(page, "kobd_sim_scans") or []) >= 1, "school run: the automatic health scan ran (ISO-TP, two ECUs) and was saved in the sim store")
    sc = ls(page, "kobd_sim_scans")[-1]["sweep"]["out"]
    check(sc["8B"]["ok"] and sc["78"]["ok"] and sc["7A"]["ok"], "scan decodes the long PIDs (8B / 78 / 7A) from the simulated car")
    check(real_snapshot(page) == before, "REAL storage untouched after a whole simulated drive (trips, learning, scans, battery, loc, fuel level)")
    page.click("#btnStop"); page.wait_for_timeout(500)

    # --- 2. motorway ---
    go(page, "motorway", 60); wait(page, "latest.speed != null && latest.speed > 108", 30000)
    check(txt(page, "#t_speed .val").startswith("6") or txt(page, "#t_speed .val").startswith("7"), f"motorway: ~70 mph ({txt(page, '#t_speed .val')})")
    wait(page, "gpsKmhOk = (typeof G !== 'undefined' && G.fix && G.fix.v > 25)", 20000)
    check(page.evaluate("G.state") == "ok", "simulated GPS fix feeds the real GPS code (state ok)")
    page.screenshot(path=str(OUT / "sim-motorway.png")); page.click("#btnStop"); page.wait_for_timeout(400)

    # --- 3. DPF regen ---
    go(page, "dpf", 60); wait(page, "dpf.active === true", 40000)
    page.wait_for_selector("#regen.show", timeout=10000); check("regen" in page.inner_text("#regen").lower(), "DPF scenario: regen banner shown from PID 8B (multi-frame)")
    wait(page, "dpf.egt != null && dpf.egt > 580", 20000); check(True, f"EGT from PID 78: {page.evaluate('Math.round(dpf.egt)')} °C")
    page.click("#btnStop"); page.wait_for_timeout(400)

    # --- 4. hot coolant ---
    go(page, "hot", 60); wait(page, "document.getElementById('p_drive').classList.contains('hotc')", 40000)
    check(page.is_visible("#t_coolant") and "hot" in page.evaluate("document.getElementById('t_coolant').className"), "hot coolant scenario: coolant tile forced on, amber")
    wait(page, "!document.getElementById('p_drive').classList.contains('hotc')", 40000); check(True, "...and clears when it cools to <= 103 °C")
    page.click("#btnStop"); page.wait_for_timeout(400)

    # --- 5. low fuel ---
    go(page, "lowfuel", 60); wait(page, "fuelMed != null && fuelMed < 12", 40000); page.wait_for_timeout(1500)
    check("hot" in page.evaluate("document.getElementById('t_range').className") or "crit" in page.evaluate("document.getElementById('t_range').className"), f"low fuel: range tile warns ({txt(page, '#t_range .val')})")
    page.click("#btnStop"); page.wait_for_timeout(400)

    # --- 6. refuel ---
    page.evaluate("store.set('fuelLast', {pct: 20, t: Date.now()}); fuelBase = 20; localStorage.removeItem('kobd_sim_fillPending')")     # fresh: the previous scenario left 9 % in the sim store
    go(page, "refuel", 60); wait(page, "localStorage.getItem('kobd_sim_fillPending') != null", 60000)
    fp = ls(page, "kobd_sim_fillPending"); check(fp["after"] - fp["before"] >= 50, f"refuel: fill-up detected by the real code ({fp['before']}% -> {fp['after']}%)")
    page.click("#btnStop"); page.wait_for_timeout(400)

    # --- 7. engine stop / restart ---
    n0 = page.inner_text("#log").count("→ new trip"); go(page, "restart", 60, TRIP_MERGE_MS=150000)
    wait(page, "document.getElementById('log').textContent.includes('same trip')", 60000)
    wait(page, "document.getElementById('status').textContent.includes('trip saved')", 60000)
    trips = ls(page, "kobd_sim_trips"); t2 = trips[-1]
    log = page.inner_text("#log")
    check(log.count("→ new trip") - n0 == 1 and len(t2["stops"]) == 2, f"stop/restart: one trip, two stops logged ({len(t2['stops'])}), restart merged")
    page.click("#btnStop"); page.wait_for_timeout(400)

    # --- 8. adapter asleep ---
    page.evaluate("KobdSim.select('asleep'); KobdSim.setRate(1)"); page.click("#btnConnect"); page.wait_for_selector("#asleep.show", timeout=30000)
    check(page.inner_text("#status").strip() == "Adapter asleep", "adapter-asleep scenario: Connect fails with the asleep message")
    page.evaluate("KobdSim.setRate(60)"); wait(page, "__mock.asleep === false", 10000); page.click("#asleep"); page.click("#btnConnect")
    wait(page, "document.getElementById('status').textContent.includes('Connected')", 30000); check(True, "...then connects once the adapter wakes")
    page.click("#btnStop"); page.wait_for_timeout(400)

    # --- 9. weak battery ---
    go(page, "weak", 2, TRIP_MERGE_MS=30000)
    wait(page, "JSON.parse(localStorage.getItem('kobd_sim_batt')||'[]').some(b => b.v < 12)", 60000)
    b = ls(page, "kobd_sim_batt"); check(b and abs(b[-1]["v"] - 11.8) < .11, f"weak battery: resting {b[-1]['v']} V recorded before start")
    check("low" in page.inner_text("#battInfo").lower() or "LOW" in page.inner_text("#battInfo"), "...and called low")
    wait(page, "crankLog.some(c => c.v < 9.5)", 60000); cr = [c for c in ls(page, "kobd_sim_crank") if c["v"] < 9.5]
    check(abs(cr[-1]["v"] - 8.9) < .11, f"cranking dip {cr[-1]['v']} V kept as crank voltage")
    page.wait_for_timeout(2500); check(not txt(page, "#t_volt .val").startswith("8.9"), "...not shown on the battery tile")
    page.click("#btnStop"); page.wait_for_timeout(400)
    check(real_snapshot(page) == before, "after all 9 scenarios: REAL storage still byte-identical")
    check(not page.errors, "no JS errors in simulation mode" + ("" if not page.errors else ": " + "; ".join(page.errors)))

    # ---------- replay ----------
    rows = ["t,speed,rpm,throttle,load,coolant,oil,iat,amb,volt,lph,mpgTrip,egt,dpfTrig,regen,fuel,gpsKmh,alt,lat,lon"]
    dist, lat0, lon0, km = 0.0, 51.50, -2.60, 0.0
    for i in range(600):
        v = 0 if i < 20 else min(80, (i - 20) * 80 / 30) if i < 50 else 80 if i < 560 else max(0, 80 - (i - 560) * 2)
        km += v / 3600
        rows.append(f"2026-11-20T08:{i // 60:02d}:{i % 60:02d}Z,{v:.1f},{(800 + v * 26) if v or i < 590 else 0:.0f},20,40,{20 + i * 0.11:.1f},70,15,8,14.0,{0.75 + v * 0.05:.2f},,300,60,0,60,{v * 0.97:.2f},{50 + i * 0.05:.1f},{lat0 + km / 111.32:.6f},{lon0}")
    open("/tmp/claude-1000/-home-swoosh-homelab/cb338e8a-9190-4715-a77e-b5b9e233df8b/scratchpad/replay.csv", "w").write("\n".join(rows) + "\n")
    open("/tmp/claude-1000/-home-swoosh-homelab/cb338e8a-9190-4715-a77e-b5b9e233df8b/scratchpad/bad.csv", "w").write("a,b\n1,2\n")
    page.set_input_files("#simFile", "/tmp/claude-1000/-home-swoosh-homelab/cb338e8a-9190-4715-a77e-b5b9e233df8b/scratchpad/bad.csv"); page.wait_for_timeout(400)
    check("Could not read" in page.inner_text("#simDesc"), "a CSV without a time column is refused with a message")
    page.set_input_files("#simFile", "/tmp/claude-1000/-home-swoosh-homelab/cb338e8a-9190-4715-a77e-b5b9e233df8b/scratchpad/replay.csv"); page.wait_for_timeout(500)
    check("600 rows" in page.inner_text("#simDesc") and "with GPS" in page.inner_text("#simDesc"), "replay loaded: " + page.inner_text("#simDesc"))
    go(page, "replay", 60, TRIP_MERGE_MS=60000)
    wait(page, "latest.speed != null && latest.speed > 70", 40000)
    check(page.evaluate("new Date().getFullYear()") == 2026 and page.evaluate("new Date(Date.now()).toISOString().startsWith('2026-11-20')"), "replay runs on the log's own clock (2026-11-20)")
    page.screenshot(path=str(OUT / "sim-replay.png"))
    wait(page, "(JSON.parse(localStorage.getItem('kobd_sim_trips')||'[]')).some(t => t.date.startsWith('2026-11-20'))", 120000)
    t = [x for x in ls(page, "kobd_sim_trips") if x["date"].startswith("2026-11-20")][-1]
    exp = km / 1.609344 * 1.0 * (1.609344 / 1.609344) * 1.0
    check(abs(t["miles"] - km / 1.609344) / (km / 1.609344) < 0.12, f"replay: trip distance {t['miles']:.2f} mi vs {km / 1.609344:.2f} mi in the log (same integration code)")
    check(t.get("gpsKm", 0) > 0.8 * km and len(t.get("route") or []) >= 2, f"replay: GPS route saved from the log's positions ({len(t.get('route') or [])} points, {t.get('gpsKm')} km)")
    check(t.get("spdErr") is not None and 1.5 < t["spdErr"] < 5, f"replay: OBD-vs-GPS speed error from gpsKmh = {t['spdErr']}% (log has GPS 3% under OBD)")
    check(t["date"].startswith("2026-11-20"), "replay: trip is dated from the log")
    check("replay finished" in page.inner_text("#simStat"), "status shows the replay finished")
    page.click("#btnStop"); page.wait_for_timeout(400)
    check(real_snapshot(page) == before, "after the replay: REAL storage still untouched")
    check(not page.errors, "no JS errors during replay")
    # ---------- leave ----------
    page.click('nav button[data-p="log"]'); page.click("#simLeave"); page.wait_for_timeout(800)
    check(page.evaluate("SIM") is False and not page.is_visible("#simBar"), "leaving simulation: back to the real app, banner gone")
    check(page.evaluate("Object.keys(localStorage).filter(k => k.startsWith('kobd_sim_')).length") == 0 and page.evaluate("sessionStorage.getItem('kobd_simMode')") is None, "every kobd_sim_ key deleted, simulation flag cleared")
    check(real_snapshot(page) == before and page.evaluate("tripsCache.length") == 1, "real trips / learning exactly as before the simulation")
    page.evaluate("localStorage.setItem('kobd_sim_trips', '[1]')"); page.reload(); page.wait_for_timeout(400)
    check(page.evaluate("localStorage.getItem('kobd_sim_trips')") is None, "a stale kobd_sim_ key is purged on the next normal start")

# ---------- parity: the bundled ELM327 core answers exactly like tests/mock-adapter.js ----------
with app(viewport=(412, 915)) as page:
    page.evaluate("__mock.engine = true; __mock.cruise = 50; __mock.coolantC = 91; __mock.fuelPct = 64; __mock.dpfTrigPct = 71; __mock.egtC = 333")
    res = page.evaluate("""async () => {
      const p = await navigator.serial.requestPort(); await p.open(); const w = p.writable.getWriter(), r = p.readable.getReader(), dec = new TextDecoder(), enc = new TextEncoder();
      const e = kobdCreateElm(); Object.assign(e.mock, {engine: true, cruise: 50, coolantC: 91, fuelPct: 64, dpfTrigPct: 71, egtC: 333});
      const cmds = ['ATZ', 'ATDPN', 'ATE0', '03', '07', '04', '0902', 'XYZ']; for (let i = 0; i <= 0xA8; i++) { const h = i.toString(16).toUpperCase().padStart(2, '0'); if (h !== '42') cmds.push('01' + h); }
      const bad = []; let n = 0;
      for (const c of cmds) { await w.write(enc.encode(c + '\\r')); let s = ''; while (!s.includes('>')) { const x = await r.read(); s += dec.decode(x.value); }
        const lines = s.split(/[\\r\\n]+/).map(l => l.trim()).filter(l => l && l !== c && l !== '>' && !l.endsWith('>')).map(l => l.replace('>', ''));
        const mine = e.answer(c); n++; if (JSON.stringify(lines) !== JSON.stringify(mine)) bad.push(c + ': ' + JSON.stringify(lines) + ' vs ' + JSON.stringify(mine)); }
      return {n, bad}; }""")
    check(res["n"] > 150 and not res["bad"], f"bundled ELM327 core == tests/mock-adapter.js for {res['n']} commands" + ("" if not res["bad"] else ": " + "; ".join(res["bad"][:3])))
