# Kodiaq OBD (v6 in progress)

Single-file PWA (`index.html`, plain JS, no build) for a Skoda Kodiaq diesel, talking to an iCar2 ELM327 over
Web Serial (Bluetooth SPP) in Chrome on Android. Offline via `sw.js`. Own git repo (origin 5w00sh/kodiaq-obd), nested inside ~/homelab.

## Hard constraints
- Single offline page: everything in `index.html` (+ `sw.js`, `manifest.json`, `icon.svg`). No CDNs, no external fonts/scripts/images, no build step.
- No secrets, tokens or personal data in the repo: it is PUBLIC.
- The Drive tab must fit with NO scrolling at 412x915, 915x412, 800x1280, 1280x800 and the system-bar sizes 800x1100, 1280x700, 412x840, 360x690, 760x320 (tests/test_layouts.py enforces it).
- Network calls only where a stage explicitly allows them (Stage 2: Overpass + Open-Meteo, no keys); GPS routes and motion data stay on the device.

## The car (from real logs, 26 Nov 2026)
- 2023 Skoda Kodiaq SE 2.0 TDI 150 DSG 4x4 (diesel). Adapter: Vgate iCar2 BT3.0, `ATZ` replies "ELM327 v2.2". Bluetooth Classic SPP only.
- `ATDPN` replies "A6" (ISO 15765-4 CAN 11-bit 500k).
- TWO ECUs answer mode 01. Real `0100` reply: `4100981B8013` and `410098180001`. Mode 03 with no codes returns `4300` twice; mode 07 returns `4700` twice.
  The old parser read the second `4300` as a code and showed fake C0300/C0700. Parse per ECU message (count byte first on CAN). Regression-tested in tests/test_dtc.py.
- Supported mode-01 PIDs: 01 04 05 0C 0D 0F 10 11 1C 1F 20 21 2F 30 31 33 40 42 45 46 49 4A 4C 51 5C 5E 60 61 62 63 65 67 69 6B 6D 70 71 77 78 7A 7F 80 83 85 88 8B 8C 8E 8F 9B 9C 9D 9E A0 A2 A4 A5 A6 A7
- Fuel source: PID 5E works (L/h). Warm idle is about 0.75 L/h at ~800 rpm.
- Battery (ATRV): engine running ~13.2-13.3 V. After engine off (ignition on, lights/blower likely on) ~11.0 V.
- Throttle (0111) and intake air (010F) are listed as supported but were blank for a whole trip in v4 (fixed in v5 by retrying).
- The iCar2 sleeps 30 min after engine off and wakes ONLY via its button: there is no auto-wake, so the app must say so clearly.
- No fault codes. Skoda-only systems (brake pads, ABS) are not visible over standard OBD.

## UI notes (v6.0)
- Themes are CSS variables on `<html data-theme=day|night data-mode=auto|day|night>`, set by an inline head script (`kobdTheme`) before first paint. Never hard-code colours: use the variables.
- Auto theme reads the cached position `kobd_loc` ({lat,lon,t}); the theme code never prompts for location. Stage 2's GPS should keep `kobd_loc` fresh.
- Tests seed `kobd_splashDay` so the splash doesn't cover buttons (`app(splash=True)` to test it).

## Drive tab layout + readability floors (v6.0.3)
- Hard floors, enforced by `tests/test_readability.py` at 360x760, 760x360, 412x915, 915x412, 800x1280, 1280x800, both themes, normal + Big mode, with the DPF banner (and fill card): speed digits >= 72 px tall (ink, measured via canvas) on phones / 96 px on tablets and always the largest number; Range miles + Trip average >= 56 px; small tiles' figures >= 32 px; secondary lines ("36 L (62%)", "£42 to full") >= 20 px and never truncated; labels >= 12 px. Tokens: `--f-speed/--f-hero/--f-small/--f-sec/--f-lab` (phone vs tablet). NEVER shrink text to fit: add/adjust a container-query tier on `.drive` so a lower-priority tile is dropped instead (priority: instant, fuel flow, rpm, coolant, score, cost, oil).
- Split Fuel hero (`#fuelhero`): `#t_range` (miles + `@NN mpg` basis) over `#t_remain` (`36 L (62%)`, `£NN to full`). Range basis: last 50 miles if >= 50 mi of trips, else the all-time trip average (even short trips), else 40 mpg.
- Big mode: speed, range, trip average, instant, fuel flow; coolant only when > 105 C (replaces fuel flow, hides the fill card).

## v6.0.4 (real Galaxy Tab S6 fixes)
- Layout height = `--vh`, set by a head script from min(innerHeight, visualViewport.height x scale) (CSS fallback 100dvh). `body` is `position:fixed` at that height; header/nav/main/splash are `absolute` inside it. The installed PWA's visible area is smaller than 1280 (status bar + taskbar).
- Tablet tiers use the tablet row heights (90 px): portrait 647/749/851/953 px, landscape 307/409 px; phone tiers 478/551/624/697 (portrait), 238/311 (landscape). The old "tablets show every tile" rule overflowed on a real tablet (Oil cut off).
- The fill-up card yields (`#p_drive.fillhide`, `fitFill()`) whenever showing it would push the grid below its minimum: regen warning > fill card.
- Not connected (load, after Stop, after Demo): `renderIdle()` blanks live tiles; trip average / trip cost / range / remaining stay, relabelled via `setStale()` ("Last trip avg", "Last trip cost", "Range · last known", "Remaining · last known"); they come from the last SAVED trip and `kobd_fuelLast`, never from Demo. Stop after Demo resets trip, fuel window, style and DPF. The loop must not repaint after Stop (guards in `loop()`).
- `#emptyHint` ("Ignition on → Connect · or tap Demo") is its own flex row above the grid, only while `body:not(.live)`.
- Hot coolant (> 105 C, clears <= 103) is visible in every mode/viewport: normal-mode tiers show it in the small row; where they would drop it, it takes Trip average's place (grid-row/column override). Big mode: replaces fuel flow, or Trip average when the small row is dropped. The hot coolant also hides the fill card.

## Fuel & range (v6.0.2)
- Litres left = PID 2F % x tank (setting `kobd_tank`, 50-70 L, default 58). Rolling median ~90 s, samples skipped while |accel| > 2 m/s^2. Range basis: see the layout section above.
- Auto fill-up: level +10 points (vs last session, or vs the lowest of the last 10 min) -> `kobd_fillPending`; the Drive card appears only after 8 s stationary. A fill to >= 92 % with a receipt feeds `recordFill()` (pump calibration); smaller top-ups are only logged. Demo never writes fuel data.

## Workflow (per stage)
Run `tests/run.sh` (all tests), show screenshots from `tests/out/`, bump `APP_VERSION` (index.html) AND the
`C` cache name in `sw.js`, commit, then WAIT for the user's OK before pushing or starting the next stage.
Never push without OK. Everything stays on-device: no logos/images from the web, GPS routes never leave the phone.

## Tests (python3 + playwright, headless Chromium; `tests/out/` is gitignored)
- Mock fuel/coolant controls: `__mock.fuelPct`, `fuelBurn` (%/min), `fuelSpike` (+/- % glitches), `coolantC`. Test hooks in the app: `window.__forceSwap`, `window.__forceFill` (layout tests only), `FUEL_WIN_MS` (shrink the 90 s median window).
- `tests/mock-adapter.js`: fake `navigator.serial` ELM327 (diesel Kodiaq PIDs); `window.__mock.asleep = true` simulates a sleeping iCar2. Extend it for mock GPS/motion.
- Mock controls: `__mock.engine` (on/off), `__mock.cruise` (km/h), `__mock.asleep`, `__mock.mode03` (override mode-03 reply lines). It answers the real two-ECU replies and the real PID list.
- `tests/test_demo.py`: Demo mode, every tab, no JS errors.
- `tests/test_connect.py`: Connect through the mock, live values, asleep adapter.
- `tests/test_layouts.py`: demo at 412x915, 915x412, 800x1280, 1280x800; fails on Drive overflow, clipped tiles, JS errors.
- `tests/test_dtc.py`: two-ECU fault-code regression (no fake C0300/C0700).
- `tests/test_theme_splash.py`: splash (text, once/day, tap skip, reduced motion), auto/day/night themes (sunrise/sunset from a permitted fix, scheme fallback, toggle, contrast), Big mode.
- `tests/test_fuel.py`: fuel left (PID 2F x tank), range (last ~50 mi / this trip / 45 mpg, all-time), low-fuel colours, smoothing, Big-mode coolant/range swap, auto fill-up detection + receipt prompt + calibration.
- `tests/test_readability.py`: the hard readability floors above, 11 viewports x 8 states (incl. hot coolant) x 2 themes.
- `tests/test_v604.py`: visualViewport sizing, idle/last-trip/last-known after Stop + Demo, hint row, hot-coolant hysteresis in every mode.
- `tests/test_engine_cycle.py`: off -> connect -> on -> off 30s+ -> on; pre-start battery, auto health scan, trip saved, new trip. ~1.5 min (real timers).
- `tests/run.sh` runs all; `FAST=1 tests/run.sh` skips the engine cycle.
- The mock honours ATS0 (no spaces in replies); the app depends on that.
