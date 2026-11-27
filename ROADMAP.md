# Kodiaq OBD roadmap

## v6.0.6 (deferred fixes from real logs)
> Status: these four items were already implemented and pushed inside v6.0.5 (commits b6c1e7f, 04a3bae). Kept here as the record; nothing left to build.
- Decode (label "experimental"): 9B "3f 80 2c 3a" AdBlue (tank temp C-40, level D*100/255) shown on Car tab; A4 gear; 77 charge-air temps (B-40, C-40); 67 coolant sensor (B-40); A2 fuel mg/stroke (/32).
- Health scan: if engine already running, note "Connect before starting the engine for a battery reading".
- Merge engine restarts within 10 min into the same trip (log the stop).
- Ignore ATRV samples within 10 s of engine start for learning/alerts; record them as "crank voltage" (battery-health data).

## Stage 2 – Phone GPS (v6.1.0) — DONE (rebased onto v6.0.5, shipped)
- As per original brief: GPS vs OBD speed (speedo error), altitude + smoothed gradient (feature in expected-mpg model), simplified route per trip (on-device), OSM maxspeed via Overpass cached ("OSM limit, may be wrong", roundel + % over limit), Open-Meteo weather at trip start (temp, wind, rain) into the mpg model.
- Degrade gracefully with no GPS / no data; GPS only while connected; keep kobd_loc fresh for auto theme; range tile + speed-limit roundel must fit at 360x760; mock GPS (hill, limit change, dropout) in tests.
- Commit locally after each sub-feature.

## Stage 2.5 – On-device simulator (v6.1.1) — DONE
- Hidden dev menu (tap version 5×): "Simulated car" connection using tests/mock-adapter.js logic bundled into the app, so the REAL code path runs (parsing, 2 ECUs, ISO-TP, scans, trips, learning, DPF).
- Scenarios: cold-start school run, motorway, DPF regen, hot coolant, low fuel, refuel, engine stop/restart, adapter asleep, weak battery.
- Replay: load a real CSV log (incl. GPS if present) and play back at 1×/10×/60× through the same pipeline; simulated GPS along the route.
- Sim data isolated (separate kobd_sim_ keys), never mixed with real trips/learning; cleared on leaving sim mode; clear "SIMULATION" banner.

## v6.1.4 – Over-limit highlight — DONE
- Speed tile: steady red ring + faint tint when OBD speed > OSM limit + tolerance (amber between limit and limit + tolerance). Tolerance: +2 mph (default) / 10% + 2 mph / exact. Red after 2 s, clears 1 mph under. Only with a known limit and GPS accuracy <= 20 m. No flashing, no sound.

## v6.1.5 – Road data recorder — DONE
- Car tab "Road mapping" (per device, default OFF): DeviceMotion -> 1 Hz rows (accel RMS/pp/jerk, gyro RMS, gravity, GPS, OBD speed, rpm) per trip in IndexedDB, ~50 MB cap with oldest-trip eviction, 30 s mount-noise sample at idle, CSV + JSON export with a GPS warning. Records only: no analysis.

## v6.1.6 – Raw road overlay map (uncalibrated) — DONE
- Vendored Leaflet 1.9.4 (`vendor/`, no CDN). OSM tiles when online with attribution (light use: visible tiles only, no preloading, never cached); offline fallback draws the route outline on a blank map. Style tab → tap a trip → map of its route. Layers: speed / roughness (raw accel RMS, green→red, labelled "uncalibrated – speed bumps not excluded"). Tap a point: time, speed, raw values. Fits and stays readable at 360x760 and 412x915.

## v6.1.7 – Auto-start, touched flag, export + map fixes — DONE
- Road mapping/GPS stay on across restarts and start on Connect (motion permission requested in the tap; a denial keeps the setting on and shows "waiting for motion permission"). `touched` per 1 Hz row (taps +-2 s, hidden/blur). Export schema 2 with units + mountNoise. Fullscreen button moved off the speed-limit roundel. Map finds road rows by time overlap; "View on map" in the Car tab.

## Stage 3 – Motion sensors + Road condition map (v6.2.0)
- Note: Stage 3 REPROCESSES the rows recorded since v6.1.5 (1 Hz aggregates in IndexedDB + the mount-noise samples): calibration, eIRI, pothole detection, speed-bump exclusion and the council report all run over stored data. It builds on the v6.1.6 map (same Leaflet view; segments coloured by eIRI instead of raw accel RMS).
- Per-device setting "Road mapping" default OFF; only on for the Pixel 10 Pro XL in a Spigen Cryomax MagFit Qi2 vent mount (Peltier fan). Devices are independent, no syncing.
- G-forces (long/lat), harsh cornering, braking in g → eco score.
- Learning/calibration: first 3 drives "calibrating" (show progress, map marked low-confidence). Continuous gravity estimation for orientation; learn mount noise floor at idle (incl. fan); learn the vent mount's resonance (FFT) and attenuate; road band ~0.5–20 Hz; normalise via repeat passes; auto re-learn if noise/resonance shifts. Warn if the mount looks loose.
- Road score: estimated IRI (eIRI, m/km) per ~25–100 m segment, speed-normalised (OBD speed), RoadLab-style, labelled "estimated". Bands <1.5 excellent, 1.5–2.7 good, 2.7–4 fair, 4–6 poor, >6 very poor; also UK-style green/amber/red. Per-road/route score (distance-weighted eIRI + pothole count), worst/best roads list, history per pass to show deterioration.
- Potholes: Pothole Patrol-style speed-normalised spike detection, confirmed across passes (Street Bump-style aggregation, confidence per segment), severity, date first seen.
- Exclude speed bumps: OBD slowdown <20 mph before + re-acceleration after; long symmetric waveform vs short sharp drop; gyro roll (both wheels = little roll); OSM traffic_calming tags nearby; consistent signature each pass; user can tag "speed bump – ignore" (remembered by location). Bumps = own layer, excluded from scores and reports.
- Map overlay: OSM street map, switchable layers (roughness, potholes, bumps, later mpg/speed limits), tap segment for details; offline fallback draws routes on blank canvas. Vendor any map library (no CDNs).
- "Report to council": builds report (date, lat/lon, severity, eIRI, map link), opens share sheet/email with CSV + GeoJSON. User reviews and sends; never auto-send. GeoJSON export for Google My Maps.
- **Stage 3 must skip rows with `touched = true`** (screen taps / page hidden) in roughness (eIRI) and pothole scoring.
- Mock motion + GPS in tests (smooth road, rough road, pothole, speed bump, loose mount).

## Stage 4 – Data
- Export all (JSON via share sheet), Import (restore/other device), all trips CSV, roughness/pothole GeoJSON; warn exports include GPS.

## Parked ideas (don't build unless asked)
- Climate/A-C cost test; Service & parts log with baseline resets + DVSA MOT history; live mirroring to a second screen.
