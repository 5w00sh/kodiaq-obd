# Kodiaq OBD roadmap

## v6.0.6 (deferred fixes from real logs)
> Status: these four items were already implemented and pushed inside v6.0.5 (commits b6c1e7f, 04a3bae). Kept here as the record; nothing left to build.
- Decode (label "experimental"): 9B "3f 80 2c 3a" AdBlue (tank temp C-40, level D*100/255) shown on Car tab; A4 gear; 77 charge-air temps (B-40, C-40); 67 coolant sensor (B-40); A2 fuel mg/stroke (/32).
- Health scan: if engine already running, note "Connect before starting the engine for a battery reading".
- Merge engine restarts within 10 min into the same trip (log the stop).
- Ignore ATRV samples within 10 s of engine start for learning/alerts; record them as "crank voltage" (battery-health data).

## Stage 2 – Phone GPS (v6.1.0, branch stage2-wip – rebase onto main)
- As per original brief: GPS vs OBD speed (speedo error), altitude + smoothed gradient (feature in expected-mpg model), simplified route per trip (on-device), OSM maxspeed via Overpass cached ("OSM limit, may be wrong", roundel + % over limit), Open-Meteo weather at trip start (temp, wind, rain) into the mpg model.
- Degrade gracefully with no GPS / no data; GPS only while connected; keep kobd_loc fresh for auto theme; range tile + speed-limit roundel must fit at 360x760; mock GPS (hill, limit change, dropout) in tests.
- Commit locally after each sub-feature.

## Stage 3 – Motion sensors + Road condition map (v6.2.0)
- Per-device setting "Road mapping" default OFF; only on for the Pixel 10 Pro XL in a Spigen Cryomax MagFit Qi2 vent mount (Peltier fan). Devices are independent, no syncing.
- G-forces (long/lat), harsh cornering, braking in g → eco score.
- Learning/calibration: first 3 drives "calibrating" (show progress, map marked low-confidence). Continuous gravity estimation for orientation; learn mount noise floor at idle (incl. fan); learn the vent mount's resonance (FFT) and attenuate; road band ~0.5–20 Hz; normalise via repeat passes; auto re-learn if noise/resonance shifts. Warn if the mount looks loose.
- Road score: estimated IRI (eIRI, m/km) per ~25–100 m segment, speed-normalised (OBD speed), RoadLab-style, labelled "estimated". Bands <1.5 excellent, 1.5–2.7 good, 2.7–4 fair, 4–6 poor, >6 very poor; also UK-style green/amber/red. Per-road/route score (distance-weighted eIRI + pothole count), worst/best roads list, history per pass to show deterioration.
- Potholes: Pothole Patrol-style speed-normalised spike detection, confirmed across passes (Street Bump-style aggregation, confidence per segment), severity, date first seen.
- Exclude speed bumps: OBD slowdown <20 mph before + re-acceleration after; long symmetric waveform vs short sharp drop; gyro roll (both wheels = little roll); OSM traffic_calming tags nearby; consistent signature each pass; user can tag "speed bump – ignore" (remembered by location). Bumps = own layer, excluded from scores and reports.
- Map overlay: OSM street map, switchable layers (roughness, potholes, bumps, later mpg/speed limits), tap segment for details; offline fallback draws routes on blank canvas. Vendor any map library (no CDNs).
- "Report to council": builds report (date, lat/lon, severity, eIRI, map link), opens share sheet/email with CSV + GeoJSON. User reviews and sends; never auto-send. GeoJSON export for Google My Maps.
- Mock motion + GPS in tests (smooth road, rough road, pothole, speed bump, loose mount).

## Stage 4 – Data
- Export all (JSON via share sheet), Import (restore/other device), all trips CSV, roughness/pothole GeoJSON; warn exports include GPS.

## Parked ideas (don't build unless asked)
- Climate/A-C cost test; Service & parts log with baseline resets + DVSA MOT history; live mirroring to a second screen.
