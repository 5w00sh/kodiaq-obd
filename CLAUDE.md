# Kodiaq OBD (v6 in progress)

Single-file PWA (`index.html`, plain JS, no build) for a Skoda Kodiaq diesel, talking to an iCar2 ELM327 over
Web Serial (Bluetooth SPP) in Chrome on Android. Offline via `sw.js`. Own git repo (origin 5w00sh/kodiaq-obd), nested inside ~/homelab.

## Hard constraints
- Single offline page: everything in `index.html` (+ `sw.js`, `manifest.json`, `icon.svg`). No CDNs, no external fonts/scripts/images, no build step.
- No secrets, tokens or personal data in the repo: it is PUBLIC.
- The Drive tab must fit with NO scrolling at 412x915, 915x412, 800x1280 and 1280x800 (tests/test_layouts.py enforces it).
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

## Workflow (per stage)
Run `tests/run.sh` (both tests), show screenshots from `tests/out/`, bump `APP_VERSION` (index.html) AND the
`C` cache name in `sw.js`, commit, then WAIT for the user's OK before pushing or starting the next stage.
Never push without OK. Everything stays on-device: no logos/images from the web, GPS routes never leave the phone.

## Tests (python3 + playwright, headless Chromium; `tests/out/` is gitignored)
- `tests/mock-adapter.js`: fake `navigator.serial` ELM327 (diesel Kodiaq PIDs); `window.__mock.asleep = true` simulates a sleeping iCar2. Extend it for mock GPS/motion.
- Mock controls: `__mock.engine` (on/off), `__mock.cruise` (km/h), `__mock.asleep`, `__mock.mode03` (override mode-03 reply lines). It answers the real two-ECU replies and the real PID list.
- `tests/test_demo.py`: Demo mode, every tab, no JS errors.
- `tests/test_connect.py`: Connect through the mock, live values, asleep adapter.
- `tests/test_layouts.py`: demo at 412x915, 915x412, 800x1280, 1280x800; fails on Drive overflow, clipped tiles, JS errors.
- `tests/test_dtc.py`: two-ECU fault-code regression (no fake C0300/C0700).
- `tests/test_engine_cycle.py`: off -> connect -> on -> off 30s+ -> on; pre-start battery, auto health scan, trip saved, new trip. ~1.5 min (real timers).
- `tests/run.sh` runs all; `FAST=1 tests/run.sh` skips the engine cycle.
- The mock honours ATS0 (no spaces in replies); the app depends on that.
