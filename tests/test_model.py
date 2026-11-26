"""Test 9: the expected-mpg model with the new features (climb, wind, rain): old trips without them still train, hills lower the expectation."""
import json
from common import app, check

with app(mock=False) as page:
    old = [{"date": f"2026-10-{i+1:02d}T08:00:00Z", "miles": 8 + i, "mpg": 48 + (i % 5), "feat": {"miles": 8 + i, "avgMph": 38 + i % 6 * 4, "mwShare": .1 * (i % 4), "amb": 8 + i % 7, "coldFrac": .1, "idleFrac": .05}} for i in range(9)]
    new = [{"date": f"2026-11-{i+1:02d}T08:00:00Z", "miles": 9 + i % 6, "mpg": 56 - 6 * (i % 4), "feat": {"miles": 9 + i % 6, "avgMph": 40 + i % 5 * 3, "mwShare": .2, "amb": 8, "coldFrac": .1, "idleFrac": .05,
            "climb": (i % 4) * 1.0, "wind": 6 + (i % 3) * 5, "rain": i % 2}} for i in range(16)]
    page.evaluate("t => localStorage.setItem('kobd_trips', JSON.stringify(t))", old)
    r = page.evaluate("(trainModel(), model.ready && model.w.every(Number.isFinite))")
    check(r is True, "9 old-style trips (no GPS fields) still train a finite model")
    page.evaluate("t => localStorage.setItem('kobd_trips', JSON.stringify(t))", old + new)
    r = page.evaluate("(trainModel(), model.ready && model.w.every(Number.isFinite) && model.w.length === 11)")
    check(r is True, "old + new trips: finite 10-feature model")
    base = {"miles": 10, "avgMph": 44, "mwShare": .2, "amb": 8, "coldFrac": .1, "idleFrac": .05}
    flat = page.evaluate("f => expectedMpg(f)", {**base, "climb": 0, "wind": 8, "rain": 0})
    hilly = page.evaluate("f => expectedMpg(f)", {**base, "climb": 3, "wind": 8, "rain": 0})
    unknown = page.evaluate("f => expectedMpg(f)", base)
    check(all(x is not None for x in (flat, hilly, unknown)) and hilly < flat - 2, f"hills lower the expected mpg ({flat:.1f} flat vs {hilly:.1f} at 3 % climb); unknown climb gives {unknown:.1f}")
    check(not page.errors, "no JS errors")
