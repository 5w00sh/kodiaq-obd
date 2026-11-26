"""Test 6: splash (once a day, tap to skip, reduced motion), themes (auto/day/night, sunrise/sunset, scheme fallback), Big mode."""
import json, datetime
from common import app, check, OUT

THEME = "document.documentElement.dataset.theme"
MODE = "document.documentElement.dataset.mode"

# ---- splash ----
with app(splash=True) as page:
    check(page.is_visible("#splash"), "splash shows on first open")
    check("Welcome Kevlar!" in page.inner_text("#splash h2"), "headline 'Welcome Kevlar!'")
    check(page.inner_text("#splash p").strip().lower() == "skoda kodiaq 4x4", "subtitle 'Skoda Kodiaq 4x4' (text only, no logo)")
    check(page.locator("#splash img, #splash image").count() == 0, "no images in the splash")
    page.wait_for_timeout(1700); page.screenshot(path=str(OUT / "splash-mid.png"))
    page.wait_for_timeout(1300)
    check(page.locator("#splash").count() == 0, "splash gone by ~3 s on its own")
    page.reload(); page.wait_for_timeout(300)
    check(page.locator("#splash").count() == 0, "not shown again the same day")
    page.evaluate("localStorage.setItem('kobd_splashDay','2000-01-01')"); page.reload(); page.wait_for_timeout(300)
    check(page.is_visible("#splash"), "shows again on a new day")
    page.mouse.click(200, 400); page.wait_for_timeout(700)
    check(page.locator("#splash").count() == 0, "tap skips it")
    check(not page.errors, "no JS errors")

with app(splash=True, reduced_motion="reduce") as page:
    page.wait_for_timeout(300); page.screenshot(path=str(OUT / "splash-reduced.png"))
    check(page.is_visible("#splash h2") and page.evaluate("getComputedStyle(document.querySelector('#splash h2')).opacity") == "1", "reduced motion: text shown statically")
    page.wait_for_timeout(1700)
    check(page.locator("#splash").count() == 0, "reduced motion: shorter splash, then gone")

# ---- theme: fallback to the phone's scheme, then the header toggle ----
for scheme, want in (("dark", "night"), ("light", "day")):
    with app(color_scheme=scheme) as page:
        check(page.evaluate(THEME) == want and page.evaluate(MODE) == "auto", f"auto, no GPS, phone is {scheme} -> {want}")
with app(color_scheme="light") as page:
    page.screenshot(path=str(OUT / "theme-auto-day.png"))
    seen = []
    for _ in range(3):
        page.click("#btnTheme"); seen.append((page.evaluate(MODE), page.evaluate(THEME)))
    check(seen == [("day", "day"), ("night", "night"), ("auto", "day")], f"toggle cycles auto -> day -> night -> auto: {seen}")
    page.click("#btnTheme"); page.reload(); page.wait_for_timeout(200)
    check(page.evaluate(MODE) == "day", "mode survives a reload")
    check(page.evaluate("document.querySelector('meta[name=theme-color]').content") == "#f2f4f7", "browser bar colour follows the theme")

# ---- contrast: day = dark on light, night = light on near-black ----
LUM = """(c)=>{const m=c.match(/[\\d.]+/g).map(Number);const f=v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)};return .2126*f(m[0])+.7152*f(m[1])+.0722*f(m[2])}"""
RATIO = f"""() => {{ const L={LUM}; const cs=getComputedStyle(document.body); const a=L(cs.color), b=L(cs.backgroundColor);
  const t=getComputedStyle(document.querySelector('.lab')).color, ml=L(t); const card=L(getComputedStyle(document.querySelector('.tile')).backgroundColor);
  return [(Math.max(a,b)+.05)/(Math.min(a,b)+.05), (Math.max(ml,card)+.05)/(Math.min(ml,card)+.05), a>b]; }}"""
for theme in ("day", "night"):
    with app(theme=theme) as page:
        r = page.evaluate(RATIO)
        check(r[0] >= 12 and r[1] >= 4.5 and r[2] == (theme == "night"), f"{theme}: text contrast {r[0]:.1f}:1, labels {r[1]:.1f}:1, {'light on dark' if r[2] else 'dark on light'}")

# ---- theme: auto from sunrise/sunset at a permitted GPS fix (Bristol, 51.45 N 2.58 W) ----
def sun_case(iso, want, label):
    with app(geolocation={"latitude": 51.45, "longitude": -2.58}, permissions=["geolocation"], timezone_id="Europe/London") as page:
        page.clock.install(time=datetime.datetime.fromisoformat(iso))
        page.reload(); page.wait_for_timeout(600)
        loc = json.loads(page.evaluate("localStorage.getItem('kobd_loc')") or "null")
        check(loc is not None and abs(loc["lat"] - 51.45) < .01, f"{label}: permitted GPS fix cached for sunrise/sunset")
        check(page.evaluate(THEME) == want, f"{label} -> {want} (theme is {page.evaluate(THEME)}, source {page.evaluate('document.documentElement.dataset.themeSrc')})")
        return page
# 26 Nov at Bristol: sunrise ~07:35, sunset ~16:10 (UTC=local in winter)
sun_case("2026-11-26T12:00:00Z", "day", "noon, 26 Nov")
sun_case("2026-11-26T21:00:00Z", "night", "9 pm, 26 Nov")
sun_case("2026-11-26T06:30:00Z", "night", "06:30, before sunrise")
sun_case("2026-11-26T17:30:00Z", "night", "17:30, after sunset")
sun_case("2026-06-21T20:30:00Z", "day", "21:30 BST midsummer (sun still up)")
with app(color_scheme="dark", geolocation={"latitude": 51.45, "longitude": -2.58}, permissions=["geolocation"]) as page:
    page.clock.install(time=datetime.datetime.fromisoformat("2026-11-26T12:00:00Z")); page.reload(); page.wait_for_timeout(600)
    check(page.evaluate(THEME) == "day", "sun beats the phone scheme: phone dark but it is noon -> day")
    page.evaluate("kobdTheme.cycle(); kobdTheme.cycle()")
    check(page.evaluate(THEME) == "night" and page.evaluate(MODE) == "night", "manual night overrides the sun")
with app(color_scheme="light", geolocation={"latitude": 51.45, "longitude": -2.58}) as page:    # GPS NOT granted
    page.wait_for_timeout(500)
    check(page.evaluate("localStorage.getItem('kobd_loc')") is None, "no permission -> theme code never asks for GPS or stores a position")

# ---- Big mode ----
with app(viewport=(412, 915)) as page:
    page.click("#btnDemo"); page.wait_for_timeout(1500)
    before = page.evaluate("parseFloat(getComputedStyle(document.querySelector('#t_speed .val')).fontSize)")
    page.click("#btnBig"); page.wait_for_timeout(400)
    after = page.evaluate("parseFloat(getComputedStyle(document.querySelector('#t_speed .val')).fontSize)")
    check(after > before * 1.15, f"big mode enlarges the numbers ({before:.0f}px -> {after:.0f}px)")
    check(not page.is_visible("#t_speed .lab") and page.is_visible("#t_speed .val"), "labels hidden, numbers shown")
    check(page.is_visible("#t_lph") and not page.is_visible("#t_rpm"), "big mode shows fuel flow (L/h) instead of RPM")
    check(page.is_visible("#t_mpgInst") and page.is_visible("#t_coolant"), "big mode keeps instant mpg and coolant")
    page.screenshot(path=str(OUT / "big-mode.png"))
    page.reload(); page.wait_for_timeout(300)
    check(page.evaluate("document.getElementById('p_drive').classList.contains('big')"), "big mode persists across reloads")
    page.click("#btnBig")
    check(page.is_visible("#t_speed .lab"), "toggles back to normal")
    check(not page.errors, "no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))

# ---- version visible on phones (header title is hidden there; the Log tab footer carries it) ----
with app(viewport=(412, 915)) as page:
    page.click('nav button[data-p="log"]'); page.wait_for_timeout(400)
    ver = page.inner_text("#verNote")
    check("v6.0" in ver and page.is_visible("#verNote"), f"version visible on a phone, Log tab footer: '{ver.strip()}'")
