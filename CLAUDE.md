# Kodiaq OBD (v6 in progress)

Single-file PWA (`index.html`, plain JS, no build) for a Skoda Kodiaq diesel, talking to an iCar2 ELM327 over
Web Serial (Bluetooth SPP) in Chrome on Android. Offline via `sw.js`. Own git repo (origin 5w00sh/kodiaq-obd), nested inside ~/homelab.

## Workflow (per stage)
Run `tests/run.sh` (both tests), show screenshots from `tests/out/`, bump `APP_VERSION` (index.html) AND the
`C` cache name in `sw.js`, commit, then WAIT for the user's OK before pushing or starting the next stage.
Never push without OK. Everything stays on-device: no logos/images from the web, GPS routes never leave the phone.

## Tests (python3 + playwright, headless Chromium; `tests/out/` is gitignored)
- `tests/mock-adapter.js`: fake `navigator.serial` ELM327 (diesel Kodiaq PIDs); `window.__mock.asleep = true` simulates a sleeping iCar2. Extend it for mock GPS/motion.
- `tests/test_demo.py`: Demo mode, every tab, no JS errors.
- `tests/test_connect.py`: Connect through the mock, live values, asleep adapter.
- The mock honours ATS0 (no spaces in replies); the app depends on that.
