"""Test 3: layouts. Demo mode at four viewports; fail on Drive-tab overflow, clipped tiles or JS errors."""
from common import app, check, OUT

VIEWPORTS = [(412, 915), (915, 412), (800, 1280), (1280, 800), (360, 760), (760, 360),     # 360x760 / 760x360: Galaxy S10
             (800, 1100), (1280, 700), (412, 840), (360, 690), (760, 320)]                  # v6.0.4: real visible sizes with Android status bar + taskbar
JS = """() => {
  const bad = [], pane = document.getElementById('p_drive'), de = document.scrollingElement;
  if (pane.scrollHeight > pane.clientHeight + 1) bad.push(`Drive pane scrolls (${pane.scrollHeight}>${pane.clientHeight})`);
  if (pane.scrollWidth > pane.clientWidth + 1) bad.push('Drive pane scrolls sideways');
  if (de.scrollHeight > innerHeight + 1 || de.scrollWidth > innerWidth + 1) bad.push('page itself scrolls');
  const fc = document.getElementById('fillCard');
  if (getComputedStyle(fc).display !== 'none') {
    const fr = fc.getBoundingClientRect();
    if (fr.bottom > pane.querySelector('.drive').getBoundingClientRect().top + 1) bad.push('fill-up card overlaps the tile grid');
    for (const e of fc.querySelectorAll('span,input,button')) { const r = e.getBoundingClientRect(); if (r.right > fr.right + 1 || r.bottom > fr.bottom + 1 || r.width < 20) bad.push('fill-up card: ' + e.id + ' clipped'); }
  }
  const lim = document.getElementById('limit');
  if (lim.classList.contains('show')) {
    const sp = document.getElementById('t_speed').getBoundingClientRect(), lr0 = lim.getBoundingClientRect(), sr = lim.querySelector('small').getBoundingClientRect(), lr = sr.width ? {left:Math.min(lr0.left,sr.left), right:Math.max(lr0.right,sr.right), top:lr0.top, bottom:Math.max(lr0.bottom,sr.bottom)} : lr0, v = document.querySelector('#t_speed .val');
    if (lr.left < sp.left || lr.right > sp.right + 1 || lr.top < sp.top || lr.bottom > sp.bottom + 1) bad.push('limit roundel outside the speed tile');
    for (const n of [v.firstChild, v.querySelector('.unit')]) { const r = document.createRange(); r.selectNode(n); const b = r.getBoundingClientRect();
      if (b.width && b.right > lr.left + 1 && b.left < lr.right && b.bottom > lr.top && b.top < lr.bottom) bad.push('limit roundel overlaps the speed number'); }
    if (lim.querySelector('small').scrollHeight > lim.querySelector('small').clientHeight + 1) bad.push('limit caption clipped');
  }
  const rg = document.getElementById('regen'), rr = rg.getBoundingClientRect(), regOn = getComputedStyle(rg).display !== 'none';
  const dr = pane.querySelector('.drive').getBoundingClientRect();
  if (regOn && rr.bottom > dr.top + 1) bad.push('regen banner overlaps the tile grid');
  const bb = document.getElementById('btnBig').getBoundingClientRect();
  if (regOn && bb.top < rr.bottom) bad.push('Big-mode button overlaps the regen banner');
  if (regOn && rg.scrollHeight > rg.clientHeight + 1) bad.push('regen banner text clipped');
  for (const t of pane.querySelectorAll('.tile')) {
    if (getComputedStyle(t).display === 'none') continue;     // tiles Big mode deliberately hides
    const r = t.getBoundingClientRect(), v = t.querySelector('.val, .sec'), l = t.querySelector('.lab'), vr = v.getBoundingClientRect();
    if (r.width < 40 || r.height < 30) bad.push(t.id + ' collapsed ' + Math.round(r.width) + 'x' + Math.round(r.height));
    if (t.scrollWidth > t.clientWidth + 1) bad.push(t.id + ' content clipped sideways');   // vertical glyph ink is checked in test_readability.py
    if (v.scrollWidth > v.clientWidth + 1) bad.push(t.id + ' number clipped');
    if (l.scrollWidth > l.clientWidth + 1) bad.push(t.id + ' label truncated');
    if (vr.bottom > r.bottom + 1 || vr.right > r.right + 1 || vr.top < r.top - 1) bad.push(t.id + ' number outside tile');
    if (r.bottom > innerHeight + 1 || r.right > innerWidth + 1) bad.push(t.id + ' off screen');
  }
  return bad;
}"""

for theme in ("night", "day"):
    for w, h in VIEWPORTS:
        with app(viewport=(w, h), mock=False, theme=theme) as page:
            page.click("#btnDemo"); page.wait_for_timeout(2500)
            page.screenshot(path=str(OUT / f"layout-{theme}-{w}x{h}.png"))
            bad = page.evaluate(JS)
            check(not bad, f"{theme} {w}x{h} Drive tab fits, no clipped tiles" + ("" if not bad else ": " + "; ".join(bad)))
            check(page.is_visible("#t_range") and page.inner_text("#t_range .num").isdigit() and "@" in page.inner_text("#t_range .basis"), f"{theme} {w}x{h} Range tile shows miles + basis ({' '.join(page.inner_text('#t_range .val').split())})")
            check(page.is_visible("#t_remain") and "L (" in page.inner_text("#remL") and "£" in page.inner_text("#remCost"), f"{theme} {w}x{h} Remaining tile: {page.inner_text('#remL')} / {page.inner_text('#remCost')}")
            page.evaluate("window.__forceFill = true"); page.wait_for_timeout(300)       # the fill-up prompt card, on top of everything else
            bad = page.evaluate(JS)
            check(not bad and page.is_visible("#fillCard"), f"{theme} {w}x{h} fill-up card: grid shrinks, nothing clipped" + ("" if not bad else ": " + "; ".join(bad)))
            page.screenshot(path=str(OUT / f"layout-{theme}-{w}x{h}-fillcard.png"))
            page.evaluate("limitUi(30)"); page.wait_for_timeout(100)                  # speed-limit roundel on for the rest of the checks
            bad = page.evaluate(JS)
            check(not bad and page.is_visible("#limit"), f"{theme} {w}x{h} limit roundel fits beside the speed" + ("" if not bad else ": " + "; ".join(bad)))
            page.screenshot(path=str(OUT / f"layout-{theme}-{w}x{h}-limit.png"))
            page.evaluate("ds = 13"); page.wait_for_timeout(900)      # demo DPF regen window -> banner on
            check(page.is_visible("#regen"), f"{theme} {w}x{h} regen banner showing")
            page.screenshot(path=str(OUT / f"layout-{theme}-{w}x{h}-regen.png"))
            bad = page.evaluate(JS)
            check(not bad, f"{theme} {w}x{h} regen banner on: grid shrinks, bottom row fully visible" + ("" if not bad else ": " + "; ".join(bad)))
            page.click("#btnBig"); page.wait_for_timeout(500)
            page.screenshot(path=str(OUT / f"layout-{theme}-{w}x{h}-big.png"))
            bad = page.evaluate(JS)
            check(page.is_visible("#regen") and not bad, f"{theme} {w}x{h} BIG mode + regen banner fits, no clipped tiles" + ("" if not bad else ": " + "; ".join(bad)))
            check(not page.is_visible("#t_speed .lab"), f"{theme} {w}x{h} big mode hides labels")
            page.evaluate("window.__forceHot = true"); page.wait_for_timeout(500)           # coolant > 105 C: it joins Big mode
            bad = page.evaluate(JS)
            check(page.is_visible("#t_range") and page.is_visible("#t_coolant") and not bad, f"{theme} {w}x{h} BIG mode + hot coolant: fits (banner + card on)" + ("" if not bad else ": " + "; ".join(bad)))
            page.screenshot(path=str(OUT / f"layout-{theme}-{w}x{h}-big-hot.png"))
            page.evaluate("window.__forceHot = false; window.__forceFill = false")
            page.click("#btnBig")
            for tab in ("style", "car", "fuel", "log"):
                page.click(f'nav button[data-p="{tab}"]'); page.wait_for_timeout(150)
                if (w, h) == (412, 915): page.screenshot(path=str(OUT / f"{theme}-{tab}.png"))
            check(not page.errors, f"{theme} {w}x{h} no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))
