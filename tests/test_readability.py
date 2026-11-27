"""Test 10: Drive-tab READABILITY FLOORS. Measures rendered sizes and FAILS if anything is smaller than the minimums, at every
viewport (360x760, 760x360, 412x915, 915x412, 800x1280, 1280x800 + the system-bar sizes 800x1100, 1280x700, 412x840, 360x690, 760x320), both themes, normal + Big mode, with the DPF regen banner showing
(and with the fill-up card on top of it, and with hot coolant forcing the coolant tile on). If something can't fit, the app drops tiles; it must never shrink text.

  Speed digits   >= 72 px tall (real digit ink height, via canvas) on phones, >= 96 px on tablets; speed is the largest number
  Range miles, Trip average   >= 56 px      Small tiles' main figures >= 32 px
  Secondary lines ("36 L (62%)", "£42 to full") >= 20 px, never truncated/ellipsed      Labels >= 12 px, never truncated
"""
from common import app, check, OUT

VIEWPORTS = [(360, 760), (760, 360), (412, 915), (915, 412), (800, 1280), (1280, 800),
             (800, 1100), (1280, 700), (412, 840), (360, 690), (760, 320)]      # v6.0.4: visible sizes with system bars (status bar + taskbar)
JS = """(big) => {
  const bad = [], info = {}, phone = Math.min(innerWidth, innerHeight) < 700, pane = document.getElementById('p_drive');
  const shown = el => !!el && getComputedStyle(el).display !== 'none' && el.getClientRects().length > 0;
  const fs = el => parseFloat(getComputedStyle(el).fontSize);
  const ink = el => { const cs = getComputedStyle(el), c = document.createElement('canvas').getContext('2d'); c.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const m = c.measureText('0123456789'); return m.actualBoundingBoxAscent + m.actualBoundingBoxDescent; };
  // real glyph ink box of a text node (the font's line box is taller than the visible digits, so scrollHeight lies)
  const inkBox = node => { const cs = getComputedStyle(node.parentElement), c = document.createElement('canvas').getContext('2d'); c.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const m = c.measureText(node.textContent), r = document.createRange(); r.selectNodeContents(node); const b = r.getBoundingClientRect(), base = b.top + m.fontBoundingBoxAscent;
    return {top: base - m.actualBoundingBoxAscent, bottom: base + m.actualBoundingBoxDescent, left: b.left, right: b.right}; };
  const inTile = (el, t, what) => { const r = el.getBoundingClientRect(), b = t.getBoundingClientRect();
    if (r.left < b.left - 1 || r.right > b.right + 1) bad.push(what + ' spills out of its tile'); };
  // --- no overflow anywhere ---
  if (pane.scrollHeight > pane.clientHeight + 1 || document.scrollingElement.scrollHeight > innerHeight + 1) bad.push('Drive tab scrolls');
  const tiles = [...pane.querySelectorAll('.tile')].filter(shown);
  for (const t of tiles) {
    const r = t.getBoundingClientRect(), v = t.querySelector('.val, .sec');
    if (r.bottom > innerHeight + 1 || r.right > innerWidth + 1) bad.push(t.id + ' off screen');
    if (t.scrollWidth > t.clientWidth + 1) bad.push(t.id + ' content clipped sideways');
    const w = document.createTreeWalker(t, NodeFilter.SHOW_TEXT);
    for (let n; (n = w.nextNode());) { if (!n.textContent.trim() || !n.parentElement.getClientRects().length) continue; const k = inkBox(n);
      if (k.top < r.top - 1 || k.bottom > r.bottom + 1 || k.left < r.left - 1 || k.right > r.right + 1) bad.push(t.id + ' text "' + n.textContent.trim().slice(0, 12) + '" ink outside the tile (' + k.top.toFixed(0) + '-' + k.bottom.toFixed(0) + ' vs ' + r.top.toFixed(0) + '-' + r.bottom.toFixed(0) + ')'); }
    if (v && v.scrollWidth > v.clientWidth + 1) bad.push(t.id + ' text clipped');
    if (v) inTile(v, t, t.id + ' text');
  }
  const lim = document.getElementById('limit');
  if (lim.classList.contains('show')) {
    const sp = document.getElementById('t_speed').getBoundingClientRect(), lr0 = lim.getBoundingClientRect(), sr = lim.querySelector('small').getBoundingClientRect(), lr = sr.width ? {left:Math.min(lr0.left,sr.left), right:Math.max(lr0.right,sr.right), top:lr0.top, bottom:Math.max(lr0.bottom,sr.bottom)} : lr0, v = document.querySelector('#t_speed .val');
    if (lr.left < sp.left || lr.right > sp.right + 1 || lr.top < sp.top || lr.bottom > sp.bottom + 1) bad.push('limit roundel outside the speed tile');
    for (const n of [v.firstChild, v.querySelector('.unit')]) { const r = document.createRange(); r.selectNode(n); const b = r.getBoundingClientRect();
      if (b.width && b.right > lr.left + 1 && b.left < lr.right && b.bottom > lr.top && b.top < lr.bottom) bad.push('limit roundel overlaps the speed number'); }
    if (lim.querySelector('small').scrollHeight > lim.querySelector('small').clientHeight + 1) bad.push('limit caption clipped');
  }
  // --- speed: must exist, big, and the largest number ---
  const sp = document.querySelector('#t_speed .val'); if (!shown(sp)) bad.push('Speed tile missing');
  else { info.speedFont = fs(sp); info.speedInk = ink(sp); const need = phone ? 72 : 96;
    if (info.speedInk < need) bad.push(`speed digits ${info.speedInk.toFixed(0)}px tall < ${need}`);
    for (const v of pane.querySelectorAll('.tile .val')) if (v !== sp && shown(v) && fs(v) >= info.speedFont) bad.push(v.parentElement.id + ' number ' + fs(v).toFixed(0) + 'px is not smaller than speed ' + info.speedFont.toFixed(0)); }
  // --- range + trip average >= 56 ---
  const rg = document.querySelector('#t_range .num'); if (!shown(rg)) bad.push('Range tile missing');
  else { info.rangeFont = fs(rg); if (fs(rg) < 56) bad.push('range miles ' + fs(rg).toFixed(0) + 'px < 56'); }
  const hotc = pane.classList.contains('hotc'), dr = pane.querySelector('.drive').getBoundingClientRect(), land = dr.width >= dr.height;
  const cool = document.getElementById('t_coolant');
  if (hotc && !shown(cool)) bad.push('hot coolant (> 105 C) is not visible');        // v6.0.4: forced visible in every mode and viewport
  const tr = document.querySelector('#t_mpgTrip .val'); if (!shown(tr)) { if (!(hotc && shown(cool))) bad.push('Trip average tile missing'); }   // hot coolant may take its place
  else { info.tripFont = fs(tr); if (fs(tr) < 56) bad.push('trip average ' + fs(tr).toFixed(0) + 'px < 56'); }
  // --- small tiles >= 32 ---
  const small = [...pane.querySelectorAll('.sm')].filter(shown); info.small = small.map(t => t.id.slice(2)).join(',');
  for (const t of small) { const f = fs(t.querySelector('.val')); if (f < 32) bad.push(t.id + ' figure ' + f.toFixed(0) + 'px < 32'); }
  // --- basis label (@NN mpg) ---
  const ba = document.querySelector('#t_range .basis'); if (!shown(ba) || !/^@\\d+ mpg$/.test(ba.textContent.trim())) bad.push('range basis label missing: ' + (ba && ba.textContent));
  else { if (fs(ba) < 14) bad.push('basis label ' + fs(ba) + 'px < 14'); inTile(ba, document.getElementById('t_range'), 'basis label'); }
  // --- remaining lines >= 20, never truncated ---
  const rem = document.getElementById('t_remain');
  if (big) { if (shown(rem)) bad.push('Big mode should not show Estimated remaining'); }
  else if (!shown(rem)) bad.push('Estimated remaining tile missing');
  else for (const id of ['remL', 'remCost']) { const e = document.getElementById(id), cs = getComputedStyle(e); info[id] = e.textContent;
    if (fs(e) < 20) bad.push(id + ' ' + fs(e).toFixed(0) + 'px < 20');
    if (e.scrollWidth > e.clientWidth + 1 || cs.textOverflow === 'ellipsis' || /…|\\.\\.\\./.test(e.textContent)) bad.push(id + ' truncated: ' + e.textContent);
    inTile(e, rem, id); }
  // --- labels >= 12, never truncated ---
  if (!big) for (const l of pane.querySelectorAll('.lab')) if (shown(l)) { if (fs(l) < 12) bad.push(l.textContent + ' label ' + fs(l) + 'px < 12'); if (l.scrollWidth > l.clientWidth + 1) bad.push('label truncated: ' + l.textContent); }
  // --- Big mode tile set ---
  if (big && (land ? dr.height > 210 : dr.height > 414) && !shown(document.getElementById('t_mpgInst'))) bad.push('t_mpgInst missing in big mode');   // below that the small row is dropped by design (never shrink text)
  info.tiles = tiles.length;
  return {bad, info};
}"""

STATES = [
    ("normal",            "ds = 0; window.__forceFill = false; window.__forceHot = false", False, False),
    ("speed limit",       "limitUi(30)", False, False),
    ("over limit (red)",   "limitUi(30); window.__forceOver = 'over'", False, False),
    ("over limit (amber)", "limitUi(30); window.__forceOver = 'amber'", False, False),
    ("regen banner",      "ds = 13; window.__forceOver = 'over'", False, True),
    ("regen + fill card", "ds = 13; window.__forceFill = true", False, True),
    ("hot coolant",       "ds = 0; window.__forceFill = false; window.__forceHot = true; window.__forceOver = null", False, False),
    ("hot + regen + fill","ds = 13; window.__forceFill = true; window.__forceHot = true", False, True),
    ("big + regen",       "ds = 13; window.__forceFill = false; window.__forceHot = false; if (!document.getElementById('p_drive').classList.contains('big')) document.getElementById('btnBig').click()", True, True),
    ("big",               "ds = 0", True, False),
    ("big + hot coolant", "ds = 0; window.__forceHot = true", True, False),
    ("big + limit",       "ds = 0; window.__forceHot = false; limitUi(60)", True, False),
]

for theme in ("night", "day"):
    for w, h in VIEWPORTS:
        with app(viewport=(w, h), mock=False, theme=theme) as page:
            page.click("#btnDemo"); page.wait_for_timeout(1200)
            for name, setup, big, banner in STATES:
                page.evaluate(setup); page.wait_for_timeout(750)
                if banner: check(page.is_visible("#regen"), f"{theme} {w}x{h} [{name}] regen banner is showing")
                r = page.evaluate(JS, big)
                i = r["info"]
                msg = f"{theme} {w}x{h} [{name}] floors met (speed {i.get('speedFont',0):.0f}px/ink {i.get('speedInk',0):.0f}, range {i.get('rangeFont',0):.0f}, trip {i.get('tripFont',0):.0f}, small tiles: {i.get('small') or 'none'})"
                if r["bad"]: msg = f"{theme} {w}x{h} [{name}]: " + "; ".join(r["bad"])
                check(not r["bad"], msg)
                if name in ("normal", "big + regen", "regen + fill card") and theme == "night": page.screenshot(path=str(OUT / f"read-{w}x{h}-{name.replace(' + ', '-').replace(' ', '-')}.png"))
            check(not page.errors, f"{theme} {w}x{h} no JS errors" + ("" if not page.errors else ": " + "; ".join(page.errors)))
