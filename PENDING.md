# Pending

## v6.1.7 (done, tick-list)
- [x] Auto-start GPS + Road mapping (persisted, permission in the Connect tap, denial keeps setting on)
- [x] 15:01 "Road mapping OFF" bug: no code path found; hardened (intent log, cookie backup, persist()) - watch `kobd_roadMapLog` if it happens again
- [x] `touched` flag on road rows (CSV/JSON/map); Stage 3 must exclude them
- [x] Export: mountNoise, units, schema 2
- [x] Speed tile: fullscreen button vs roundel overlap + layout test
- [x] Map: lookup by time overlap, "View on map", live trip, Leaflet error message, sw precache

## Open
- [ ] Confirm on the Pixel after deploying v6.1.7: Road mapping stays on after an update.
