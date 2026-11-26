"""Test 3: layouts. Demo mode at four viewports; fail on Drive-tab overflow, clipped tiles or JS errors."""
from common import app, check, OUT

VIEWPORTS = [(412, 915), (915, 412), (800, 1280), (1280, 800)]
JS = """() => {
  const bad = [], pane = document.getElementById('p_drive'), de = document.scrollingElement;
  if (pane.scrollHeight > pane.clientHeight + 1) bad.push(`Drive pane scrolls (${pane.scrollHeight}>${pane.clientHeight})`);
  if (pane.scrollWidth > pane.clientWidth + 1) bad.push('Drive pane scrolls sideways');
  if (de.scrollHeight > innerHeight + 1 || de.scrollWidth > innerWidth + 1) bad.push('page itself scrolls');
  for (const t of pane.querySelectorAll('.tile')) {
    if (getComputedStyle(t).display === 'none') continue;     // tiles Big mode deliberately hides
    const r = t.getBoundingClientRect(), v = t.querySelector('.val'), l = t.querySelector('.lab'), vr = v.getBoundingClientRect();
    if (r.width < 40 || r.height < 30) bad.push(t.id + ' collapsed ' + Math.round(r.width) + 'x' + Math.round(r.height));
    if (t.scrollHeight > t.clientHeight + 1 || t.scrollWidth > t.clientWidth + 1) bad.push(t.id + ' content clipped');
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
            page.click("#btnBig"); page.wait_for_timeout(500)
            page.screenshot(path=str(OUT / f"layout-{theme}-{w}x{h}-big.png"))
            bad = page.evaluate(JS)
            check(not bad, f"{theme} {w}x{h} BIG mode fits, no clipped tiles" + ("" if not bad else ": " + "; ".join(bad)))
            check(not page.is_visible("#t_speed .lab"), f"{theme} {w}x{h} big mode hides labels")
            page.click("#btnBig")
            for tab in ("style", "car", "fuel", "log"):
                page.click(f'nav button[data-p="{tab}"]'); page.wait_for_timeout(150)
                if (w, h) == (412, 915): page.screenshot(path=str(OUT / f"{theme}-{tab}.png"))
            check(not page.errors, f"{theme} {w}x{h} no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))
