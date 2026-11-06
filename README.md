# Parcel Sort Cell Sizer

A pre-sales sizing tool for robotic parcel sort cells: from a delivery station's real parcel data, how many cells clear the dispatch waves on a busy day, and what share of parcels a robot can handle.

**Live demo:** DEMO_URL_PLACEHOLDER

## The problem
Robotic sort systems are sold one site at a time, and each proposal needs a cell count and a business case. The usual spreadsheet divides the day's volume by the sort window. Outbound departures come in waves, though, and the waves concentrate inbound into short peaks.

## What it shows (measured on 1.46 M real packages, six stations)
- **The wave.** Clustered real route departures push peak 15-minute inbound to 1.45–1.96× the shift average. A bank sized on average throughput is one cell short of a first-come-first-served bank at 3 of 6 stations. One cell short leaves 5.5–34% of parcels late on the design day, and 64–100% of routes with a late parcel.
- **Deadline-aware induction.** A scheduling lower bound (processor-demand criterion) gives the fewest cells any policy could use. Earliest-cutoff-first induction reaches that floor at all six stations and saves one cell over FIFO at four of them (24 against 28 cells), subject to destinations per cell.
- **Dollars, with no price assumed.** Manual sorters are simulated under the same wave and late-parcel rule. At one operator per cell, a cell at the largest station pays back in 24 months if it costs under about $35k, or about $59k with one operator per two cells. At two operators per cell, labour alone never pays back.
- **What flips the count.** Sweeping each assumption shows the order to measure on a site visit: sustained cell rate (flips about 11% below nameplate), peak uplift, then the inbound arrival curve. Service-time variability never changes the count.
- **A data catch.** In this public sample, daily volume tracks the number of routes sampled (correlation 0.99–1.00). So the design day is built from routes × packages per route, with day-block bootstrap intervals, and the "busy-day ratio" is reported as a sampling artefact rather than demand.
- **Pick-envelope fit.** 96.4–97.7% of parcels fit a 60 × 45 × 35 cm envelope (an editable assumption). Moving the longest-side limit by 5 cm changes that by under half a point.

## How it works
- `pipeline/sizer/ingest.py` streams the 375 MB package file (ijson, NaN-safe) into a compact table; the parsed count reconciles exactly with the raw file.
- `envelope.py`: vectorised box-envelope fit on sorted dimensions, with a sensitivity sweep.
- `queueing.py`: the hand rule `ceil(V(1-e)/(T·r))` and Erlang C (kept as a stability check; at a 30-minute threshold it reduces to the hand rule).
- `sim.py`: exact G/G/c FIFO discrete-event simulation and an earliest-deadline-first variant, with wave arrivals tied to real route departures.
- `deadline.py`: processor-demand lower bound on cells for any induction policy.
- `robust.py`: coverage diagnostics, day-block bootstrap, bootstrap design days.
- `business.py`: manual-equivalent labour, annual delta, break-even capex per cell.
- Results are precomputed to `public/data/*.json`; the web page is static and needs no API keys.

See [METHOD.md](METHOD.md) for equations, assumptions, validation (hand calculations, bound ≤ EDF ≤ FIFO ladder, DES vs M/M/c theory, Little's law, factor-split holdout), sensitivity flip points and limitations.

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
