#!/usr/bin/env bash
# Run every test; screenshots land in tests/out/. Needs: python3 + playwright (chromium installed).
# Fast tests first; the engine-cycle test takes ~1.5 min (real 30 s engine-off timer). FAST=1 skips it.
set -e
cd "$(dirname "$0")"
python3 test_demo.py
python3 test_connect.py
python3 test_layouts.py
python3 test_dtc.py
python3 test_theme_splash.py
python3 test_fuel.py
python3 test_readability.py
[ -n "$FAST" ] || python3 test_engine_cycle.py
