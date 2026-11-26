// Mock iCar2 / ELM327 for tests. Injected BEFORE the page scripts (Playwright add_init_script).
// Fakes navigator.serial with a port that talks ELM327 and answers a believable diesel Kodiaq.
// Control it from a test via window.__mock (e.g. __mock.asleep = true makes port.open() fail).
// Later stages extend this file with mock GPS and device-motion helpers.
(() => {
  const mock = window.__mock = {
    asleep: false,          // true -> port.open() rejects, like an iCar2 whose light is off
    engine: true,           // false -> rpm 0, speed 0, no fuel flow; battery reads the ignition-on/engine-off value
    hasRun: false,          // set when the engine has been on (drives the 11.0 V after-engine-off reading)
    cruise: null,           // number -> constant speed (km/h) while the engine is on; null -> sinusoid 20..90
    fuelPct: 70,            // PID 2F tank level in %. Tests set this directly (a refuel = a jump)
    fuelBurn: 0,            // % lost per minute while the engine runs (slow drift down)
    fuelSpike: 0,           // every 4th read adds +/- this many % (slosh / glitch) to test the smoothing
    coolantC: 90,           // PID 05
    dpfTrigPct: 62,         // PID 8B byte C (soot %), multi-frame
    dpfRegen: false,        // PID 8B status bit
    oilRaw: null,           // PID 5C raw byte override (255 = sensor not ready, the first sample after a restart on the real car)
    crankUntil: 0,          // ms timestamp: until then every voltage reads 10.0 (cranking dip)
    egtC: 280,              // PID 78 sensor temps, multi-frame
    mode03: null,           // array of reply lines to override the default "4300" x2 (no codes)
    restVolt: 12.4,         // ATRV before the engine has ever run (ignition on, rested battery)
    openAttempts: 0,
    log: [],                // every command received
    t0: Date.now(),
    speedKmh() { if (!this.engine) return 0; if (this.cruise != null) return this.cruise; const t = (Date.now() - this.t0) / 1000; return Math.max(0, Math.round(55 + 35 * Math.sin(t / 6))); },
    rpm() { return this.engine ? Math.round(800 + this.speedKmh() * 26) : 0; },
    volt() { if (Date.now() < this.crankUntil) return 10.0; if (this.engine) { this.hasRun = true; return 13.2 + (Date.now() % 3) / 10; } return this.hasRun ? 11.0 : this.restVolt; },
  };

  // ---------------------------------------------------------------------------------------------
  // Mock phone GPS (opt-in: tests set window.__MOCK_GPS = {...} before the page loads).
  // A simulated vehicle drives due north from (lat0, lon0), then turns east at bendAt metres, at __mock.gps.speed m/s; altitude follows a hill:
  // flat 50 m to 100 m, +6 % from 100 m to 400 m (=> +18 m), flat after. Controls (all on __mock.gps):
  //   permission 'granted'|'prompt'|'denied', promptAnswer 'allow'|'deny'|'dismiss', prompts (count), available (false = no fix),
  //   dropout (true = silent GPS dropout), acc (metres), speed (m/s), dist (m travelled), watches/polls (call logs).
  // Options: {unsupported:true} removes navigator.geolocation (a Wi-Fi-only tablet with no location hardware at all).
  // ---------------------------------------------------------------------------------------------
  if (window.__MOCK_GPS) {
    const o = window.__MOCK_GPS === true ? {} : window.__MOCK_GPS;
    const g = mock.gps = Object.assign({
      permission: 'granted', promptAnswer: 'allow', prompts: 0, available: true, dropout: false, acc: 8, speed: 0, dist: 0,
      lat0: 51.4545, lon0: -2.5879, watches: [], polls: [], cleared: 0, _w: new Map(), _id: 1,
      altAt(d) { return 50 + (d < 100 ? 0 : d < 400 ? (d - 100) * 0.06 : 18); },
      bendAt: 600,                  // metres: the road turns from north to east here
      fix(acc) { const d = this.dist, n = Math.min(d, this.bendAt), lat = this.lat0 + n / 111320, lon = this.lon0 + Math.max(0, d - this.bendAt) / (111320 * Math.cos(lat * Math.PI / 180));
        return { coords: { latitude: lat, longitude: lon, accuracy: acc != null ? acc : this.acc,
        altitude: this.altAt(d), altitudeAccuracy: 6, speed: this.speed, heading: d > this.bendAt ? 90 : 0 }, timestamp: Date.now() }; },
      active() { return this._w.size; }, activeHigh() { return [...this._w.values()].filter(w => w.high).length; },
    }, o);
    const err = (cb, code) => cb && cb({ code, message: 'mock ' + code });
    const gate = (okCb, errCb) => {           // permission rules shared by watch + one-shot
      if (g.permission === 'prompt') { g.prompts++;
        if (g.promptAnswer === 'dismiss') { setTimeout(() => err(errCb, 1), 10); return false; }          // closed the dialog: stays 'prompt'
        g.permission = g.promptAnswer === 'allow' ? 'granted' : 'denied'; }
      if (g.permission === 'denied') { setTimeout(() => err(errCb, 1), 10); return false; }
      return true;
    };
    setInterval(() => {
      g.dist += g.speed * 1;                                   // the vehicle keeps moving even while the GPS is out
      if (!g.available || g.dropout || g.permission !== 'granted') return;
      for (const w of g._w.values()) w.ok(g.fix());
    }, 1000);
    const geo = {
      watchPosition(ok, e, opts) { const id = g._id++; g.watches.push({ id, high: !!(opts && opts.enableHighAccuracy), at: Date.now() });
        if (!gate(ok, e)) return id; g._w.set(id, { ok, high: !!(opts && opts.enableHighAccuracy) }); return id; },
      clearWatch(id) { if (g._w.delete(id)) g.cleared++; },
      getCurrentPosition(ok, e, opts) { g.polls.push({ high: !!(opts && opts.enableHighAccuracy), at: Date.now() });
        if (!gate(ok, e)) return; if (!g.available || g.dropout) { setTimeout(() => err(e, 2), 30); return; }
        setTimeout(() => ok(g.fix(opts && opts.enableHighAccuracy ? g.acc : Math.max(g.acc, 500))), 30); },
    };
    const perms = navigator.permissions;
    const origQuery = perms && perms.query ? perms.query.bind(perms) : null;
    const queryMock = async (d) => (d && d.name === 'geolocation') ? { get state() { return g.permission; }, onchange: null, addEventListener() {} } : (origQuery ? origQuery(d) : { state: 'prompt' });
    try { Object.defineProperty(navigator, 'permissions', { value: { query: queryMock }, configurable: true }); } catch (e) {}
    if (o.unsupported) { try { delete Navigator.prototype.geolocation; } catch (e) {} try { Object.defineProperty(navigator, 'geolocation', { value: undefined, configurable: true }); } catch (e) {} delete navigator.geolocation; }
    else Object.defineProperty(navigator, 'geolocation', { value: geo, configurable: true });
  }
  const hexb = (...b) => b.map(x => (x & 255).toString(16).padStart(2, '0').toUpperCase()).join('');  // ATS0: no spaces
  // supported-PID bitmask for one 32-PID block: PID base+i+1 -> bit i from MSB
  const mask = (base, pids) => {
    let m = 0; for (const p of pids) { const i = p - base - 1; if (i >= 0 && i < 32) m |= (1 << (31 - i)) >>> 0; }
    return [(m >>> 24) & 255, (m >>> 16) & 255, (m >>> 8) & 255, m & 255];
  };
  // Real supported list from the car (26 Nov 2026). ECU 1 = engine (7E8), ECU 2 = gearbox (7E9) answers a subset.
  const SUP = [0x01,0x04,0x05,0x0C,0x0D,0x0F,0x10,0x11,0x1C,0x1F,0x20,0x21,0x2F,0x30,0x31,0x33,0x40,0x42,0x45,0x46,0x49,0x4A,0x4C,0x51,0x5C,0x5E,0x60,0x61,0x62,0x63,0x65,0x67,0x69,0x6B,0x6D,0x70,0x71,0x77,0x78,0x7A,0x7F,0x80,0x83,0x85,0x88,0x8B,0x8C,0x8E,0x8F,0x9B,0x9C,0x9D,0x9E,0xA0,0xA2,0xA4,0xA5,0xA6,0xA7];
  const SUP2 = [0x01, 0x04, 0x05, 0x0C, 0x0D, 0x20];
  const rawBytes = (n) => Array(n).fill(0);
  // Long PIDs the real car answers multi-frame (ISO-TP) from the engine ECU, and again from the gearbox ECU. Data bytes after "41 <pid>".
  const LONG = { 0x69: 7, 0x70: 10, 0x71: 6, 0x78: 9, 0x7A: 7, 0x7F: 13, 0x83: 5, 0x85: 10, 0x88: 13, 0x8B: 7, 0x8C: 16, 0x8F: 5, 0x9C: 9, 0xA7: 8 };
  function longData(pid) {
    const n = LONG[pid], d = Array.from({ length: n }, (_, i) => (pid + i * 7) & 0x7F);   // recognisable filler, never 0xEE
    if (pid === 0x8B) { d[0] = 0x01; d[1] = mock.dpfRegen ? 1 : 0; d[2] = Math.round(mock.dpfTrigPct * 255 / 100); d[3] = 0x00; d[4] = 0x1E; d[5] = 0x00; d[6] = 0x0F; }
    if (pid === 0x78) { d[0] = 0x0F; for (let i = 0; i < 4; i++) { const v = Math.round((mock.egtC + i * 5 + 40) * 10); d[1 + i * 2] = v >> 8; d[2 + i * 2] = v & 255; } }
    if (pid === 0x7A) { d[0] = 0x01; d[1] = 0x01; d[2] = 0xC2; }       // 4.5 kPa
    return d;
  }
  function isoTp(pid, data) {   // ATH0 + ATS0: "00B" length line, then "0:" (6 data bytes) and "1:".. (7 each)
    const all = [0x41, pid, ...data], lines = [all.length.toString(16).toUpperCase().padStart(3, '0')];
    for (let i = 0, n = 0; i < all.length; n++) { const take = n === 0 ? 6 : 7; lines.push((n & 15).toString(16).toUpperCase() + ':' + hexb(...all.slice(i, i + take))); i += take; }
    return lines;
  }
  function answer(c) {          // -> array of reply lines, one per answering ECU (ATH0, ATS0)
    c = c.trim().toUpperCase();
    if (c === 'ATZ') return ['ELM327 v2.2'];
    if (c.startsWith('AT')) return [c === 'ATRV' ? mock.volt().toFixed(1) + 'V' : c === 'ATDPN' ? 'A6' : 'OK'];
    const m = /^01([0-9A-F]{2})$/.exec(c);
    if (m) {
      const pid = parseInt(m[1], 16), sp = mock.speedKmh(), rpm = mock.rpm();
      const head = '41' + m[1];
      if (pid % 0x20 === 0) {
        if (pid === 0) return ['4100981B8013', '410098180001'];       // verbatim from the real car
        const l1 = hexb(...mask(pid, SUP)), l2 = hexb(...mask(pid, SUP2));
        return SUP.some(p => p > pid && p <= pid + 0x20) ? [head + l1, head + l2] : [head + l1];
      }
      if (!SUP.includes(pid)) return ['NO DATA'];
      if (LONG[pid]) return [...isoTp(pid, longData(pid)), ...isoTp(pid, Array(LONG[pid]).fill(0xEE))];   // engine ECU first, gearbox ECU's own multi-frame reply second
      switch (pid) {
        case 0x9B: return [head + '3F802C3A'];            // verbatim from the real car: DEF temp C-40, level D*100/255
        case 0xA4: return [head + '01000000'];            // gear
        case 0x77: return [head + '0352590000'];          // charge-air temps B-40, C-40
        case 0x67: return [head + '016F00'];              // coolant sensor B-40
        case 0xA2: return [head + '00EC'];                // fuel mg/stroke /32
        case 0x04: return [head + hexb(mock.engine ? 90 : 0)];
        case 0x05: return [head + hexb(mock.coolantC + 40)];
        case 0x0C: return [head + hexb((rpm * 4) >> 8, (rpm * 4) & 255)];
        case 0x0D: return [head + hexb(sp)];
        case 0x0F: return [head + hexb(20 + 40)];
        case 0x11: return [head + hexb(mock.engine ? 60 : 0)];
        case 0x46: return [head + hexb(8 + 40)];
        case 0x5C: return [head + hexb(mock.oilRaw != null ? mock.oilRaw : 88 + 40)];
        case 0x5E: { const v = mock.engine ? Math.round((0.75 + sp * 0.05) * 20) : 0; return [head + hexb(v >> 8, v & 255)]; }
        case 0x10: { const v = mock.engine ? 400 + sp * 10 : 0; return [head + hexb(v >> 8, v & 255)]; }
        case 0x1F: return [head + hexb(0, 120)];
        case 0x42: { const v = Math.round(mock.volt() * 1000); return [head + hexb(v >> 8, v & 255)]; }
        case 0x51: return [head + hexb(4)];
        case 0x1C: return [head + hexb(6)];
        case 0x2F: { mock._f = (mock._f || 0) + 1; const t = (Date.now() - mock.t0) / 60000, drift = mock.engine ? mock.fuelBurn * t : 0;
          const spike = mock.fuelSpike && mock._f % 4 === 0 ? (mock._f % 8 === 0 ? 1 : -1) * mock.fuelSpike : 0;
          return [head + hexb(Math.max(0, Math.min(255, Math.round((mock.fuelPct - drift + spike) * 255 / 100))))]; }
        case 0x33: return [head + hexb(100)];
        default: return [head + hexb(...rawBytes(pid === 0x01 ? 4 : 2))];
      }
    }
    if (c === '03') return mock.mode03 || ['4300', '4300'];                              // no codes, two ECUs: the old fake-C0300 bug
    if (c === '07') return ['4700', '4700'];
    if (c === '04') return ['44', '44'];
    return ['NO DATA'];
  }
  class Port {
    constructor() { this._q = []; this._wait = null; this._open = false; }
    async open() {
      mock.openAttempts++;
      if (mock.asleep) throw new DOMException('Failed to open serial port.', 'NetworkError');
      this._open = true;
      const self = this;
      this.readable = { getReader() { return {
        read() { return new Promise(res => { if (self._q.length) res({ value: self._q.shift(), done: false }); else self._wait = res; }); },
        releaseLock() {} }; } };
      this.writable = { getWriter() { return {
        async write(bytes) {
          for (const c of new TextDecoder().decode(bytes).split('\r').filter(Boolean)) {
            mock.log.push(c);
            setTimeout(() => self._push(c + '\r' + answer(c).join('\r') + '\r\r>'), 15);
          }
        }, releaseLock() {} }; } };
    }
    _push(s) { const v = new TextEncoder().encode(s); if (this._wait) { const w = this._wait; this._wait = null; w({ value: v, done: false }); } else this._q.push(v); }
    async close() { this._open = false; }
  }
  const serial = { async requestPort() { return new Port(); }, addEventListener() {}, removeEventListener() {} };
  Object.defineProperty(navigator, 'serial', { value: serial, configurable: true });
})();
