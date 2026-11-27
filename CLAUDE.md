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

## v6.0.5 (first real health scan)
- Long mode-01 PIDs (69 70 71 78 7A 7F 83 85 88 8B 8C 8F 9C A7) come back multi-frame (ISO-TP): a 3-hex-digit length line, then `0:` `1:` frames, per ECU. `pidReply(lines, pid)` (used by `readPid` and `rawPid`) runs `groupMsgs` and takes the first message starting `41<pid>` (engine ECU first). Never parse mode-01 replies line by line again: it silently broke DPF status (8B), EGT (78) and DPF dP (7A).
- Coolant "not at normal temp" only after >= 15 min running (PID 1F, else the trip clock) AND >= 5 miles above 30 mph (`trip.fastKm`); otherwise an OK line "still warming up". 75 C after 8 min of idling at 4 C outside is normal. > 105 C still says hot.
- Experimental decoders (`DEC`, labelled "(experimental)", unverified formulas from real raw values): 9B `3f 80 2c 3a` = AdBlue level D*100/255 (tank temp C-40) -> Car tab tile `#t_adblue`; A4 gear = byte A; 77 charge-air B-40 / C-40; 67 coolant sensor B-40; A2 mg/stroke = (256A+B)/32. The scan lists them with their raw bytes.
- Scan verdict has an `info` level. Engine already running at scan time -> "Connect before starting the engine for a battery reading" (no fake battery-before-start). The scan re-reads rpm/speed/coolant first so the state is right even before the loop's first pass.
- Mock (`tests/mock-adapter.js`): the long PIDs answer multi-frame from the engine ECU then again from the gearbox ECU (filler 0xEE, must never win); 8B/78/7A carry real structure (`__mock.dpfTrigPct`, `dpfRegen`, `egtC`); 9B/A4/77/67/A2 use the real raw values.

### v6.0.5 data hygiene (items 5-8)
- Temperatures: `tempC(raw)` -> null for raw 255 (0xFF = sensor not ready; oil showed 215 C after each restart) and anything outside -40..150 C. Used by PIDS (coolant/iat/oil/amb) and every temperature decoder; `show()` also refuses them on the tiles; `learnValue` never learns them; the scan keeps them as raw only ("sensor not ready, ignored"). Exhaust temps (PID 78) are legitimately hot and not clamped.
- Trips: engine off > `TRIP_STOP_MS` (30 s) = a logged stop, the trip is PAUSED (status "trip paused", nothing saved). A restart within `TRIP_MERGE_MS` (10 min) continues the same trip ("same trip" log line, `trip.stops` records each stop and its length). Only after 10 min off (or Stop / connection lost) is it saved. Tests shrink both with `TRIP_STOP_MS = ...; TRIP_MERGE_MS = ...`.
- Demo never logs samples (`record()` returns early, CSV disabled); a real connect and Stop-after-Demo purge any `demo`-tagged samples.
- Battery: `trackStart()` notes the rpm rise from ~0; `handleVolt(v)` is the single place ATRV samples go. Within 10 s of start (`CRANK_WINDOW_MS`) a sample is a cranking dip: kept in `kobd_crank` (lowest per start) and shown in the Car tab battery panel as "Crank voltage", never on the tile, in `latest.volt`, in pidStats or alerts. `sweep()` ignores ATRV and PID 42 during the window. Mock: `__mock.crankUntil`, `__mock.oilRaw`.

## v6.1.0 Stage 2: phone GPS (optional, degrades silently)
- GPS only while connected or in Demo (`gpsStart()/gpsStop()`), foreground only; high-accuracy watch while moving, released after `GPS_IDLE_MS` stationary (occasional low-accuracy look, Car tab says "resting"). Permission asked once (`kobd_gpsAsked`); the Car tab switch asks again. Approximate-only fixes (Wi-Fi tablet) give weather + theme (`kobd_loc` kept fresh) but no speed/hills/limits.
- Car tab "Phone GPS": GPS speed, OBD-vs-GPS error %, altitude, smoothed gradient. Trips save gpsKm, ascent/descent, a simplified route (<=150 pts, rounded), spdErr, overPct and weather `wx`; climb/wind/rain are extra (nullable) features of the expected-mpg model (old trips still train).
- OSM speed limit via Overpass (tile cache `kobd_osm_*`, ~100 m rounded queries, never the exact position), shown as a roundel inside the speed tile (`#limit`, `limitUi(v)`; -1 = national limit) captioned "OSM limit (may be wrong)"; Style tab "Over OSM limit". Weather: Open-Meteo once at trip start, cached `kobd_wx`. `sw.js` ignores cross-origin requests.
- Layout: the roundel must never overlap the speed digits or leave the speed tile at any tested viewport (test_layouts + test_readability "speed limit"/"big + limit" states).
- Tests: `test_gps.py`, `test_gps_degrade.py`, `test_model.py`; `common.app(gps=..., net=...)` stubs the network (Overpass/weather), `overpass_fixture()`, `WEATHER`; mock GPS in `mock-adapter.js` (`window.__MOCK_GPS`, `__mock.gps`: hill, limit change, dropout, coarse, permission states).

## v6.1.1 Stage 2.5: on-device simulator
- Unlock: tap the version (Log tab footer / header) 5x -> Developer section -> "Enter simulation mode" (sets `sessionStorage kobd_simMode`, reloads). `SIM`/`KP` globals come from a prelude script: in sim every `store`/osm key uses `kobd_sim_` (real keys untouched; head-script `loc` also follows `KP`). Any normal start, and "Leave simulation", deletes all `kobd_sim_*`. A "SIMULATION" strip (`#simBar`, `--simh`) shows under the header.
- `kobdCreateElm()` is a COPY of tests/mock-adapter.js's ELM327 core (+ `mock.ov` overrides, `crankV/runV/crankLen`, `mock.rate`). `tests/test_sim.py` compares both for 176 commands: change one, change the other. `KobdSim` (sim only) adds the virtual clock (`Date.now`/`performance.now` run at 1x/10x/60x; transport timeouts use `realNow`), scenarios (school, motorway, dpf, hot, lowfuel, refuel, restart, asleep, weak), CSV replay (`t` ISO + the columns this app exports; optional `lat`/`lon`; `gpsKmh`/`alt` used if present) and simulated GPS (`navigator.geolocation`/`permissions` replaced in sim).
- Connect in sim runs the real code path (`KobdSim.requestPort()` returns a Port to the bundled ELM core). Scenario starts at the first Connect and keeps running across Stop/Connect; "Restart" resets. The app's CSV export has no lat/lon, so replays of this app's own logs get a synthetic GPS route.

## v6.1.2 version visibility + update toast
- The version (`#verNote`, "Kodiaq OBD vX") is a sticky row at the TOP of the Log tab (`#verRow`), so it is never under the bottom nav and shows in the installed app at every size. 5 taps on it (or on the header version where visible) unlock the developer menu; nothing on screen advertises that.
- `sw.js` no longer calls `skipWaiting()` on install. The page registers it (https, or `window.__KOBD_SW` in tests), and when a new worker is waiting and there is a controller it shows `#updToast` "Update available – tap to reload"; the tap posts `SKIP_WAITING`, `controllerchange` reloads. Never reloads by itself (a drive may be in progress). Bump the `sw.js` cache name with every `APP_VERSION`.
- `tests/test_v612.py` (headless Chromium cannot emulate display-mode, so it fakes `matchMedia('(display-mode: standalone)')`; the app does not depend on display-mode) + a real service worker served with a changing `sw.js` for the toast.

## v6.1.3 pre-start battery reading
- Connect with the engine off starts `pre` (in `loop()` via `preStartTick()`): several ATRV reads over ~5 s (>= 3), then the engine must stay < 300 rpm for 10 s MORE before the MEDIAN is recorded (`recordBattery`). Status shows "Hold off starting for 10 s for a battery reading" meanwhile. If the engine starts first (rpm >= 300 or `startAt` set), one extra immediate read is taken and the lowest sample, if < 12.0 V, is kept as crank voltage (`recordCrank`); otherwise "no resting reading kept". Engine already running at connect: no measurement. Stop clears it.
- Real time per case ~16 s: tests wait for `kobd_batt` instead of 1.5 s. The simulator delays every scenario's engine start by `S.lead` (35 s, or 1.6 x rate) so scenarios can finish the measurement (`asleep` excepted).
- `tests/test_v613.py`: median with an outlier, start right after Connect (crank, no resting reading), start inside the 10 s hold, engine already running, Stop while measuring.

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
- `tests/test_isotp.py`: ISO-TP parser (spaces/no spaces, two ECUs), all 14 long PIDs through the mock, DPF/EGT/dP decode, health scan (nothing silent), experimental decoders, AdBlue tile, coolant rule, battery-reading message.
- `tests/test_robust.py`: tempC / 0xFF / >150 C never shown or learned, short-stop trip merging (+ stops list), demo samples out of the CSV, cranking-dip voltage kept apart.
- `tests/test_sim.py`: dev-menu unlock, sim isolation (real storage byte-identical), all 9 scenarios through the real pipeline at 60x, CSV replay with GPS, leaving simulation, bundled ELM core == tests mock.
- `tests/test_v613.py`: pre-start battery measurement (median, hold-off message, crank reclassification).
- `tests/test_v612.py`: version row visible/pinned at 360x760, 412x915, 360x690, 760x360; 5-tap unlock on it; update toast with a real service worker.
- `tests/test_v604.py`: visualViewport sizing, idle/last-trip/last-known after Stop + Demo, hint row, hot-coolant hysteresis in every mode.
- `tests/test_engine_cycle.py`: off -> connect -> on -> off 30s+ (paused) -> on (same trip) -> off past the merge window (saved once, 2 stops) -> on (new trip); pre-start battery, auto health scan. ~1.5 min (real timers).
- `tests/run.sh` runs all; `FAST=1 tests/run.sh` skips the engine cycle.
- The mock honours ATS0 (no spaces in replies); the app depends on that.
