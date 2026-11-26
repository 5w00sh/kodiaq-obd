"""Shared helpers: serve the app over http://localhost, launch headless Chromium, mock adapter injected."""
import http.server, threading, functools, pathlib, sys, contextlib, json
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "out"
OUT.mkdir(exist_ok=True)

@contextlib.contextmanager
def app(viewport=(412, 915), mock=True, splash=False, theme=None, gps=None, net=None, **ctx):
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    h.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with sync_playwright() as p:
        b = p.chromium.launch()
        c = b.new_context(viewport={"width": viewport[0], "height": viewport[1]}, **ctx)
        if gps is not None:   # mock phone GPS: True or a dict of options (see mock-adapter.js)
            c.add_init_script(f"window.__MOCK_GPS = {json.dumps(gps)};")
        if mock:
            c.add_init_script(path=str(ROOT / "tests" / "mock-adapter.js"))
        # Network stub: tests never touch the internet. page.net['overpass'] / ['weather'] = JSON to serve (None = fail), ['offline'] = fail everything.
        netstate = {"log": [], "offline": False, "overpass": None, "weather": None}
        netstate.update(net or {})
        def _route(route):
            url = route.request.url
            if url.startswith("http://127.0.0.1"): return route.continue_()
            netstate["log"].append({"method": route.request.method, "url": url, "body": route.request.post_data})
            body = None
            if "overpass-api.de" in url: body = netstate["overpass"]
            elif "open-meteo.com" in url: body = netstate["weather"]
            if netstate["offline"] or body is None: return route.abort()
            route.fulfill(status=200, content_type="application/json", headers={"access-control-allow-origin": "*"}, body=json.dumps(body))
        c.route("**/*", _route)
        if not splash:   # splash is shown once a day: mark it as already seen so it never covers the buttons
            c.add_init_script("try{ if(!localStorage.getItem('kobd_splashDay')) localStorage.setItem('kobd_splashDay', new Date().toLocaleDateString('sv')); }catch(e){}")
        if theme:        # force a theme mode for the run
            c.add_init_script(f"try{{ localStorage.setItem('kobd_themeMode', '{theme}'); }}catch(e){{}}")
        page = c.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: errors.append(f"console.error: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)
        page.errors = errors
        page.net = netstate
        page.goto(f"http://127.0.0.1:{srv.server_port}/index.html")
        try:
            yield page
        finally:
            b.close(); srv.shutdown()

FAILS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        if __import__("os").environ.get("KEEP_GOING"): FAILS.append(msg)
        else: sys.exit(1)


# --- shared GPS test fixtures ---------------------------------------------------------------
LAT0, LON0 = 51.4545, -2.5879
def overpass_fixture():
    """Two roads running north along the mock vehicle's line: a 30 mph road for the first ~150 m, then a 60 mph road."""
    d = lambda m: LAT0 + m / 111320
    way = lambda lim, a, b: {"type": "way", "tags": {"highway": "residential", "maxspeed": lim},
                             "geometry": [{"lat": d(m), "lon": LON0} for m in range(a, b + 1, 25)]}
    return {"elements": [way("30 mph", -100, 150), way("60 mph", 150, 3000),
                         {"type": "way", "tags": {"highway": "service", "maxspeed": "20 mph"}, "geometry": [{"lat": LAT0 + 0.01, "lon": LON0 + 0.01}, {"lat": LAT0 + 0.011, "lon": LON0 + 0.01}]}]}
WEATHER = {"current": {"temperature_2m": 7.5, "wind_speed_10m": 14.0, "precipitation": 0.4, "weather_code": 61}}
