#!/usr/bin/env bash
# Reproduce every number: download (once), ingest, analyse, validate, test.
set -euo pipefail
cd "$(dirname "$0")"
RAW="${1:-$HOME/Developer/job-hunt-builds/_downloads/almrrc}"
B=https://amazon-last-mile-challenges.s3.us-west-2.amazonaws.com/almrrc2021/almrrc2021-data-training/model_build_inputs
mkdir -p "$RAW"
for f in route_data.json package_data.json; do [ -s "$RAW/$f" ] || curl -sS -o "$RAW/$f" "$B/$f"; done
export SIZER_CACHE="${SIZER_CACHE:-$RAW/derived}"
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
.venv/bin/python -I scripts/ingest.py "$RAW"
.venv/bin/python -I scripts/analyse.py
.venv/bin/python -I scripts/validate.py > /dev/null
.venv/bin/python -m pytest -q
