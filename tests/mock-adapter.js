// Mock iCar2 / ELM327 for tests. Injected BEFORE the page scripts (Playwright add_init_script).
// Fakes navigator.serial with a port that talks ELM327 and answers a believable diesel Kodiaq.
// Control it from a test via window.__mock (e.g. __mock.asleep = true makes port.open() fail).
// Later stages extend this file with mock GPS and device-motion helpers.
(() => {
  const mock = window.__mock = {
    asleep: false,          // true -> port.open() rejects, like an iCar2 whose light is off
    openAttempts: 0,
    log: [],                // every command received
    t0: Date.now(),
    speedKmh() { const t = (Date.now() - this.t0) / 1000; return Math.max(0, Math.round(55 + 35 * Math.sin(t / 6))); },
    rpm() { return Math.round(800 + this.speedKmh() * 26); },
  };
  const hexb = (...b) => b.map(x => (x & 255).toString(16).padStart(2, '0').toUpperCase()).join('');  // ATS0: no spaces
  // supported-PID bitmask for one 32-PID block: PID base+i+1 -> bit i from MSB
  const mask = (base, pids) => {
    let m = 0; for (const p of pids) { const i = p - base - 1; if (i >= 0 && i < 32) m |= (1 << (31 - i)) >>> 0; }
    return [(m >>> 24) & 255, (m >>> 16) & 255, (m >>> 8) & 255, m & 255];
  };
  const SUP = [0x04, 0x05, 0x0C, 0x0D, 0x0F, 0x11, 0x20, 0x40, 0x46, 0x5C, 0x5E];
  function answer(c) {
    c = c.trim().toUpperCase();
    if (c === 'ATZ') return 'ELM327 v1.5';
    if (c.startsWith('AT')) {
      if (c === 'ATRV') return '14.1V';
      if (c === 'ATDPN') return 'A6';
      return 'OK';
    }
    const m = /^01([0-9A-F]{2})$/.exec(c);
    if (m) {
      const pid = parseInt(m[1], 16), sp = mock.speedKmh(), rpm = mock.rpm();
      const head = '41' + m[1];
      if (pid % 0x20 === 0 && SUP.some(p => p > pid && p <= pid + 0x20)) return head + hexb(...mask(pid, SUP));
      switch (pid) {
        case 0x04: return head + hexb(90);
        case 0x05: return head + hexb(90 + 40);
        case 0x0C: return head + hexb((rpm * 4) >> 8, (rpm * 4) & 255);
        case 0x0D: return head + hexb(sp);
        case 0x0F: return head + hexb(20 + 40);
        case 0x11: return head + hexb(60);
        case 0x46: return head + hexb(8 + 40);
        case 0x5C: return head + hexb(88 + 40);
        case 0x5E: { const v = Math.round((1.2 + sp * 0.05) * 20); return head + hexb(v >> 8, v & 255); }
      }
    }
    if (c === '03') return '4300';
    return 'NO DATA';
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
            setTimeout(() => self._push(c + '\r' + answer(c) + '\r\r>'), 15);
          }
        }, releaseLock() {} }; } };
    }
    _push(s) { const v = new TextEncoder().encode(s); if (this._wait) { const w = this._wait; this._wait = null; w({ value: v, done: false }); } else this._q.push(v); }
    async close() { this._open = false; }
  }
  const serial = { async requestPort() { return new Port(); }, addEventListener() {}, removeEventListener() {} };
  Object.defineProperty(navigator, 'serial', { value: serial, configurable: true });
})();
