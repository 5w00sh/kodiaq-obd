"""Shared helpers: serve the app over http://localhost, launch headless Chromium, mock adapter injected."""
import http.server, threading, functools, pathlib, sys, contextlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "out"
OUT.mkdir(exist_ok=True)

@contextlib.contextmanager
def app(viewport=(412, 915), mock=True, splash=False, theme=None, **ctx):
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    h.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with sync_playwright() as p:
        b = p.chromium.launch()
        c = b.new_context(viewport={"width": viewport[0], "height": viewport[1]}, **ctx)
        if mock:
            c.add_init_script(path=str(ROOT / "tests" / "mock-adapter.js"))
        if not splash:   # splash is shown once a day: mark it as already seen so it never covers the buttons
            c.add_init_script("try{ if(!localStorage.getItem('kobd_splashDay')) localStorage.setItem('kobd_splashDay', new Date().toLocaleDateString('sv')); }catch(e){}")
        if theme:        # force a theme mode for the run
            c.add_init_script(f"try{{ localStorage.setItem('kobd_themeMode', '{theme}'); }}catch(e){{}}")
        page = c.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: errors.append(f"console.error: {m.text}") if m.type == "error" else None)
        page.errors = errors
        page.goto(f"http://127.0.0.1:{srv.server_port}/index.html")
        try:
            yield page
        finally:
            b.close(); srv.shutdown()

def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: sys.exit(1)
