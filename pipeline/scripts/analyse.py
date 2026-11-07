"""Steps 2-6: volume profile, envelope fit, destinations, sizing (Erlang C, hand calc, DES), export.

The per-station work lives in sizer/site.py::size_station(), shared with scripts/size_site.py."""
import json, os, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sizer import config as C  # noqa: E402
from sizer.envelope import share  # noqa: E402
from sizer.site import size_station  # noqa: E402

OUT = Path(os.environ.get("SIZER_CACHE", ROOT / "out"))  # intermediate tables
WEB = ROOT.parent / "public" / "data"
WEB.mkdir(parents=True, exist_ok=True)
meta = json.loads((OUT / "routes.json").read_text())
z = np.load(OUT / "packages.npz")
R, ri, zi, dims = meta["routes"], z["route_i"], z["zone_i"], z["dims"]
zone_names = meta["zone_names"]
pk_per_route = np.bincount(ri, minlength=len(R))
station = np.array([r["station"] for r in R]); date = np.array([r["date"] for r in R])
rng = np.random.default_rng(20211)


stations = [s for s, n in sorted(((s, len(set(date[station == s]))) for s in set(station)), key=lambda t: -t[1]) if n >= 28]
stations = sorted(stations, key=lambda s: -pk_per_route[station == s].sum())[:6]
summary = []
for s in stations:
    rec, row = size_station(s, R, ri, zi, dims, zone_names, pk_per_route, station, date, rng, verbose=True)
    (WEB / f"station-{s}.json").write_text(json.dumps(rec))
    summary.append(row)

allsd = dims
summary_doc = {"stations": summary, "assumptions": {k: getattr(C, k) for k in dir(C) if k.isupper()},
               "dataset": {"name": "Amazon Last Mile Routing Research Challenge 2021 (training split)",
                           "url": "https://registry.opendata.aws/amazon-last-mile-challenges/", "licence": "CC BY-NC 4.0",
                           "routes": len(R), "packages": int(len(dims)), "stations": int(len(set(station))),
                           "dates": [min(date), max(date)], "reconciliation": meta["reconciliation"],
                           "all_sortable_share": share(allsd, **C.ENVELOPE)}}
(WEB / "summary.json").write_text(json.dumps(summary_doc, indent=1, default=float))
