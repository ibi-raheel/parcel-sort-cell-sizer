# Parcel Sort Cell Sizer

A pre-sales sizing tool for robotic parcel sort cells: from a delivery station's real parcel data, how many cells clear the dispatch waves on a busy day, and what share of parcels a robot can handle.

**Live demo:** DEMO_URL_PLACEHOLDER

## The problem
Robotic sort systems are sold one site at a time, and each proposal needs a cell count and a business case. The usual spreadsheet sizes on average daily volume. That under-builds: busy days run well above the mean, and outbound departures come in waves that concentrate inbound into short peaks.

## What it shows (measured on 1.46 M real packages)
- **Volume profile.** The P90 day is 1.30 to 1.71 times the mean day across six stations.
- **Pick-envelope fit.** 96.4% to 97.7% of parcels fit a 60 × 45 × 35 cm envelope (an editable assumption). Moving the longest-side limit by 5 cm changes that by under half a point.
- **Cell sizing.** At +10% peak with under 1% of parcels late, a wave-shaped discrete-event simulation needs 3 to 7 cells per station. Sizing on the average day gives 2 to 5, short at 5 of 6 stations. Steady-state P90 sizing (Erlang C, which agrees with the hand rule) is still one cell short at 4 of 6.

## How it works
- `pipeline/sizer/ingest.py` streams the 375 MB package file (ijson, NaN-safe) into a compact table; the parsed count reconciles exactly with the raw file.
- `envelope.py`: vectorised box-envelope fit on sorted dimensions, with a sensitivity sweep.
- `queueing.py`: Erlang C (M/M/c) and the hand rule `ceil(V(1-e)/(T·r))`.
- `sim.py`: exact G/G/c FIFO discrete-event simulation with wave arrivals tied to real route departures.
- Results are precomputed to `public/data/*.json`; the web page is static and needs no API keys.

See [METHOD.md](METHOD.md) for equations, assumptions, validation (hand calculation, DES vs Erlang C, Little's law, time holdout) and limitations.

## Run locally
```bash
npm install
npm run dev

# pipeline (Python 3.12)
cd pipeline && uv venv -p 3.12 .venv && uv pip install -p .venv numpy scipy ijson pytest
./run_all.sh          # downloads ~450 MB once, then ingest, analyse, validate, test
```

## Data
Amazon Last Mile Routing Research Challenge 2021 training data, [registry.opendata.aws/amazon-last-mile-challenges](https://registry.opendata.aws/amazon-last-mile-challenges/), licensed CC BY-NC 4.0 (Amazon.com, Inc. and MIT CTL). Volumes are packages on the routes in the public sample, not total station throughput. Inbound arrival timing is not in the dataset; it is a stated assumption tied to the real departure times. Wages: BLS OEWS (public domain). Cell and manual sort rates are published industry figures.

---
Built by Ibi Raheel, mechanical engineer building AI tools. More work at [ibiraheel.com](https://ibiraheel.com).
