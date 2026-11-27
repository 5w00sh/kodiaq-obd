"""Test 15 (v6.1.2): the version is visible in the installed app at phone sizes (pinned row at the top of the Log tab), 5 taps on it unlock the developer menu,
and "Update available - tap to reload" appears when a new service worker is waiting. Standalone display-mode cannot be emulated by headless Chromium, so the test fakes
matchMedia('(display-mode: standalone)') + navigator.standalone (nothing in the app depends on display-mode: the row shows in every mode)."""
import http.server, threading, functools, pathlib
from playwright.sync_api import sync_playwright
from common import app, check, OUT, ROOT

STANDALONE = """(() => { const mm = window.matchMedia.bind(window);
  window.matchMedia = q => /display-mode:\\s*standalone/.test(q) ? { matches: true, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, onchange: null } : mm(q);
  Object.defineProperty(navigator, 'standalone', { value: true, configurable: true }); })();"""
VP = (360, 760), (412, 915), (360, 690), (760, 360)

for w, h in VP:
    with app(viewport=(w, h), mock=False) as page:
        page.context.add_init_script(STANDALONE); page.reload(); page.wait_for_timeout(400)
        check(page.evaluate("matchMedia('(display-mode: standalone)').matches"), f"{w}x{h}: running as standalone (emulated)")
        page.click('nav button[data-p="log"]'); page.wait_for_timeout(500)
        v = page.evaluate("APP_VERSION"); n = page.evaluate("""() => { const r = document.getElementById('verNote').getBoundingClientRect(), nav = document.querySelector('nav').getBoundingClientRect(), m = document.querySelector('main').getBoundingClientRect();
            return {txt: document.getElementById('verNote').textContent, top: r.top, bottom: r.bottom, navTop: nav.top, mainTop: m.top, w: r.width, vis: r.width > 0 && r.height > 0}; }""")
        check(n["txt"] == "Kodiaq OBD v" + v and n["vis"], f"{w}x{h}: version text visible: '{n['txt']}'")
        check(n["top"] >= n["mainTop"] - 1 and n["bottom"] <= n["navTop"] and n["top"] < n["mainTop"] + 30, f"{w}x{h}: it sits at the top of the Log tab (y {n['top']:.0f}), clear of the bottom nav (nav at {n['navTop']:.0f})")
        page.evaluate("document.getElementById('p_log').scrollTop = 99999"); page.wait_for_timeout(200)
        n2 = page.evaluate("(() => { const r = document.getElementById('verNote').getBoundingClientRect(), m = document.querySelector('main').getBoundingClientRect(); return r.top - m.top; })()")
        check(0 <= n2 < 30, f"{w}x{h}: still pinned in view after scrolling the Log tab down")
        page.evaluate("document.getElementById('p_log').scrollTop = 0")
        if (w, h) in ((360, 760), (412, 915)): page.screenshot(path=str(OUT / f"v612-version-{w}x{h}.png"))
        # 5 taps on the visible version text
        for _ in range(4): page.click("#verNote")
        check(not page.is_visible("#devMenu"), f"{w}x{h}: 4 taps on the version: developer menu still hidden")
        page.click("#verNote"); page.wait_for_timeout(300)
        check(page.is_visible("#devMenu") and "Enter simulation mode" in page.inner_text("#devMenu"), f"{w}x{h}: the 5th tap on the visible version unlocks the developer menu")
        check(page.evaluate("document.getElementById('verRow').textContent").count("developer") == 0, f"{w}x{h}: nothing on screen advertises the hidden menu")
        check(not page.errors, f"{w}x{h}: no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))

# ---------- update toast: a real service worker, then a changed sw.js ----------
BUILD = {"n": 1}
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k): pass
    def do_GET(self):
        if self.path.split("?")[0] == "/sw.js":
            body = (ROOT / "sw.js").read_bytes() + f"\n// test build {BUILD['n']}\n".encode()
            self.send_response(200); self.send_header("Content-Type", "text/javascript"); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body); return
        super().do_GET()
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
with sync_playwright() as p:
    b = p.chromium.launch()
    for w, h in ((360, 760), (412, 915)):
        BUILD["n"] = 1
        c = b.new_context(viewport={"width": w, "height": h}, service_workers="allow")
        c.add_init_script(STANDALONE); c.add_init_script("window.__KOBD_SW = true; try{ if(!localStorage.getItem('kobd_splashDay')) localStorage.setItem('kobd_splashDay', new Date().toLocaleDateString('sv')); }catch(e){}")
        page = c.new_page(); errs = []; page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(f"http://127.0.0.1:{srv.server_port}/index.html")
        page.wait_for_function("navigator.serviceWorker.controller != null", timeout=20000)
        page.wait_for_timeout(500)
        check(not page.is_visible("#updToast"), f"{w}x{h}: no update toast on a fresh install / up-to-date app")
        page.evaluate("window.__marker = 'same-page'")
        BUILD["n"] = 2                                                       # a new version is deployed
        page.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update())")
        page.wait_for_selector("#updToast.show", timeout=20000)
        t = page.evaluate("""() => { const r = document.getElementById('updToast').getBoundingClientRect(), nav = document.querySelector('nav').getBoundingClientRect(); return {txt: document.getElementById('updToast').textContent, l: r.left, r: r.right, b: r.bottom, navTop: nav.top, w: innerWidth, h: r.height}; }""")
        check(t["txt"] == "Update available – tap to reload", f"{w}x{h}: toast when a new service worker is waiting: '{t['txt']}'")
        check(t["l"] >= 0 and t["r"] <= t["w"] and t["b"] <= t["navTop"] and t["h"] >= 44, f"{w}x{h}: toast is on screen, above the nav, tappable ({t['h']:.0f}px tall)")
        page.screenshot(path=str(OUT / f"v612-update-toast-{w}x{h}.png"))
        page.wait_for_timeout(2500)
        check(page.evaluate("window.__marker") == "same-page", f"{w}x{h}: the page is NOT reloaded behind the user's back (a drive in progress is safe)")
        page.click("#updToast")
        page.wait_for_function("window.__marker === undefined", timeout=20000)
        page.wait_for_timeout(800)
        check(page.evaluate("window.__marker") is None and not page.is_visible("#updToast"), f"{w}x{h}: tapping the toast swaps to the new version and reloads; toast gone")
        check(page.evaluate("navigator.serviceWorker.getRegistration().then(r => !r.waiting)"), f"{w}x{h}: no worker left waiting")
        check(not errs, f"{w}x{h}: no JS errors" + ("" if not errs else ": " + "; ".join(errs)))
        c.close()
    b.close()
srv.shutdown()
