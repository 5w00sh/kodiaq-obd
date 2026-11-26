"""Test 1: Demo mode renders every tab with no JS errors (no adapter needed)."""
from common import app, check, OUT

with app(mock=False) as page:
    page.click("#btnDemo")
    page.wait_for_timeout(3000)
    check(page.inner_text("#status").strip() == "Demo", "status shows Demo")
    check(page.inner_text("#t_speed .val").strip() not in ("", "–"), "speed tile has a value")
    page.screenshot(path=str(OUT / "demo-drive.png"))
    for tab in ("style", "car", "fuel", "log"):
        page.click(f'nav button[data-p="{tab}"]'); page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / f"demo-{tab}.png"))
    page.click("#btnStop")
    page.wait_for_timeout(300)
    check(not page.errors, "no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))
