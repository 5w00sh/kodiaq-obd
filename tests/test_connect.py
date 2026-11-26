"""Test 2: full Connect flow against the mock ELM327: init, PID discovery, live values, asleep adapter."""
from common import app, check, OUT

with app() as page:
    page.click("#btnConnect")
    page.wait_for_function("document.getElementById('status').textContent.includes('Connected')", timeout=20000)
    check(True, "connected through mock adapter")
    page.wait_for_timeout(4000)
    sp = page.inner_text("#t_speed .val").split()[0]
    check(sp not in ("", "–"), f"speed tile live ({sp} mph)")
    check(page.inner_text("#t_rpm .val").strip() not in ("", "–"), "rpm tile live")
    cmds = page.evaluate("__mock.log")
    check("ATZ" in cmds and "010D" in cmds and "010C" in cmds, "init + PID commands sent")
    page.screenshot(path=str(OUT / "connect-drive.png"))
    page.click("#btnStop"); page.wait_for_timeout(300)
    check(not page.errors, "no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))

with app() as page:
    page.evaluate("__mock.asleep = true")
    page.click("#btnConnect")
    page.wait_for_timeout(2500)
    check(page.evaluate("__mock.openAttempts") >= 1, "asleep adapter: open attempted and failed")
    page.screenshot(path=str(OUT / "connect-asleep.png"))
