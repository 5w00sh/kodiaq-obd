#!/usr/bin/env bash
# Run both tests; screenshots land in tests/out/. Needs: python3 + playwright (chromium installed).
set -e
cd "$(dirname "$0")"
python3 test_demo.py
python3 test_connect.py
