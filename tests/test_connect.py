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
    page.wait_for_selector("#asleep.show", timeout=20000)
    check(page.evaluate("__mock.openAttempts") == 3, "asleep adapter: 3 open attempts, then gave up")
    txt = " ".join(page.inner_text("#asleep").split())
    check(txt.startswith("Adapter asleep – press the button on the iCar2, then tap Connect"), "on-screen message: " + txt[:70])
    check(page.inner_text("#status").strip() == "Adapter asleep", "header status says Adapter asleep")
    page.click('nav button[data-p="fuel"]')
    check(page.is_visible("#asleep"), "message stays visible on other tabs")
    page.click('nav button[data-p="drive"]'); page.wait_for_timeout(500)   # let the tab fade-in finish
    page.screenshot(path=str(OUT / "connect-asleep.png"))
    check(page.evaluate("document.getElementById('status').scrollWidth <= document.getElementById('status').clientWidth"), "header status text not truncated")
    page.click("#asleep"); page.wait_for_timeout(100)
    check(not page.is_visible("#asleep"), "tap dismisses the asleep message")
    page.click("#btnConnect")
    page.wait_for_selector("#asleep.show", timeout=20000)       # still asleep: message comes back
    check(True, "still asleep -> message shown again on the next failed Connect")
    page.evaluate("__mock.asleep = false")
    page.click("#btnConnect")
    page.wait_for_function("document.getElementById('status').textContent.includes('Connected')", timeout=20000)
    check(not page.is_visible("#asleep"), "message clears once the adapter is awake and connected")
    check(not page.errors, "no JS errors")
