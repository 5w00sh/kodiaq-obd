"""Test 4: multi-ECU fault-code regression. Two ECUs both answer "4300"/"4700" (no codes): must NOT show C0300/C0700."""
from common import app, check, OUT

def read_codes(page):
    page.click("#btnConnect")
    page.wait_for_function("document.getElementById('status').textContent.includes('Connected')", timeout=20000)
    page.click('nav button[data-p="car"]'); page.wait_for_timeout(300)
    page.click("#btnRead")
    page.wait_for_function("document.getElementById('dtcs').textContent.trim().length > 0 && !document.getElementById('dtcs').textContent.includes('Read failed')", timeout=15000)
    page.wait_for_timeout(500)
    return page.inner_text("#dtcs")

with app() as page:
    txt = read_codes(page)
    page.screenshot(path=str(OUT / "dtc-none.png"))
    check("No fault codes" in txt, "two ECUs, no codes -> 'No fault codes'")
    check("C0300" not in txt and "C0700" not in txt, "no fake C0300/C0700")
    check(not page.errors, "no JS errors")

with app() as page:
    page.evaluate("__mock.mode03 = ['43010401', '4300']")     # ECU 1: one code P0401, ECU 2: none
    txt = read_codes(page)
    page.screenshot(path=str(OUT / "dtc-one.png"))
    check("P0401" in txt and "C0300" not in txt, "one real code on ECU 1 shows P0401 only: " + txt.replace("\n", " "))
