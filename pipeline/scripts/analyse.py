"""Steps 2-6: volume profile, envelope fit, destinations, sizing (Erlang C, hand calc, DES), export."""
import json, math, os, sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sizer import config as C  # noqa: E402
from sizer.envelope import share, sweep_longest, within  # noqa: E402
from sizer.queueing import cells_erlang, cells_hand  # noqa: E402
from sizer.sim import miss_curve  # noqa: E402

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


def hms(s):
    h, m, x = map(int, s.split(":")); return h * 3600 + m * 60 + x


stations = [s for s, n in sorted(((s, len(set(date[station == s]))) for s in set(station)), key=lambda t: -t[1]) if n >= 28]
stations = sorted(stations, key=lambda s: -pk_per_route[station == s].sum())[:6]
summary, all_days_under = [], []
for s in stations:
    rmask = station == s
    days = sorted(set(date[rmask]))
    vol = np.array([pk_per_route[rmask & (date == d)].sum() for d in days])
    mean, p50, p90 = vol.mean(), np.percentile(vol, 50), np.percentile(vol, 90)
    pkg_mask = rmask[ri]
    sd = dims[pkg_mask]
    env_share = share(sd, **C.ENVELOPE)
    exc = 1 - env_share
    l_vals = list(range(40, 81, 2))
    sweep = sweep_longest(sd, l_vals, C.ENVELOPE["max_m"], C.ENVELOPE["max_s"])
    # destinations per day: distinct zone prefix (text before the '.') and full zones
    dest = []
    for d in days:
        m = pkg_mask & (date[ri] == d)
        zs = {zone_names[k] for k in np.unique(zi[m]) if isinstance(zone_names[k], str)} - {"NA"}
        dest.append({"date": d, "zones": len(zs), "prefixes": len({x.split(".")[0] for x in zs}), "routes": int((rmask & (date == d)).sum())})
    # design day = observed day closest to P90, scaled to the +10% peak
    di = int(np.argmin(np.abs(vol - p90))); dday = days[di]
    routes_d = np.where(rmask & (date == dday))[0]
    deps = np.array([hms(R[i]["departure_utc"]) for i in routes_d], float)
    deps = deps - deps.min() + 4 * 3600  # shift: first departure at t = 4 h
    counts = np.round(pk_per_route[routes_d] * (1 + C.PEAK_UPLIFT) * (1 - exc)).astype(int)
    v_design = counts.sum() / (1 - exc)
    span_h = (deps.max() - deps.min()) / 3600 + (C.INBOUND_OPEN_H - C.INBOUND_CLOSE_H)
    lam = counts.sum() / span_h; mu = C.CELL_RATE_H
    slack_h = C.INBOUND_CLOSE_H - C.CUTOFF_H
    c_hand = cells_hand(v_design, span_h, C.CELL_RATE_H, exc)
    c_hand_mean = cells_hand(mean * (1 + C.PEAK_UPLIFT), span_h, C.CELL_RATE_H, exc)
    c_erl = cells_erlang(lam, mu, slack_h, C.MISS_TARGET)
    cvals = list(range(max(1, c_hand - 2), c_hand + 12))
    curve = miss_curve(rng, deps, counts, C.CUTOFF_H, C.INBOUND_OPEN_H, C.INBOUND_CLOSE_H, C.CELL_RATE_H, C.SERVICE_CV, cvals, reps=8)
    c_des = next((p["cells"] for p in curve if p["miss_share"] < C.MISS_TARGET), None)
    # wave profile: inbound parcels per 15 min (expected, from the uniform-per-route assumption)
    edges = np.arange(deps.min() - C.INBOUND_OPEN_H * 3600, deps.max() + 1, 900)
    prof = np.zeros(len(edges) - 1)
    for d, n in zip(deps, counts):
        a, b = d - C.INBOUND_OPEN_H * 3600, d - C.INBOUND_CLOSE_H * 3600
        ov = np.clip(np.minimum(edges[1:], b) - np.maximum(edges[:-1], a), 0, None)
        prof += n * ov / (b - a)
    max_prefix = max(x["prefixes"] for x in dest)
    design_routes = len(routes_d)  # one sort destination (gaylord / cart) per outbound route
    rec = {
        "station": s, "metro": s[:3], "days": len(days),
        "daily": [{"date": d, "packages": int(v)} for d, v in zip(days, vol)],
        "volume": {"mean": round(mean), "p50": round(p50), "p90": round(p90), "max": int(vol.max()),
                   "p90_peak": round(p90 * (1 + C.PEAK_UPLIFT)),
                   "days_above_mean_share": float((vol > mean).mean()),
                   "p90_over_mean": float(p90 / mean)},
        "packages_total": int(pkg_mask.sum()),
        "envelope": {"default": C.ENVELOPE, "sortable_share": env_share, "sweep_longest": {"l_cm": l_vals, "share": sweep},
                     "pts_per_5cm_at_default": 100 * (share(sd, **{**C.ENVELOPE, "max_l": C.ENVELOPE["max_l"] + 5}) - share(sd, **{**C.ENVELOPE, "max_l": C.ENVELOPE["max_l"] - 5})) / 2},
        "dims_quantiles_cm": {q: np.percentile(sd, q, axis=0).round(1).tolist() for q in (10, 50, 90, 99)},
        "destinations": dest, "max_zone_prefixes": max_prefix,
        "design_day": {"date": dday, "observed_packages": int(vol[di]), "design_packages": round(v_design),
                       "robot_packages": int(counts.sum()), "routes": len(routes_d),
                       "departure_spread_h": float((deps.max() - deps.min()) / 3600), "sort_span_h": span_h,
                       "lambda_per_h": lam, "wave_profile_15min": prof.round(1).tolist(),
                       "peak_15min_rate_per_h": float(prof.max() * 4)},
        "sizing": {"cells_hand_p90": c_hand, "cells_hand_mean": c_hand_mean, "cells_erlang": c_erl,
                   "cells_des": c_des, "cells_for_destinations": math.ceil(design_routes / C.GAYLORDS_PER_CELL), "cells_for_zone_prefixes": math.ceil(max_prefix / C.GAYLORDS_PER_CELL), "des_curve": curve},
    }
    # sample of sorted dims for the interactive envelope (integer mm/10 -> cm, 6000 parcels)
    samp = rng.choice(np.where(pkg_mask)[0], size=min(6000, pkg_mask.sum()), replace=False)
    rec["envelope"]["sample_cm"] = np.round(dims[samp]).astype(int).tolist()
    rec["envelope"]["sample_share"] = share(dims[samp], **C.ENVELOPE)
    (WEB / f"station-{s}.json").write_text(json.dumps(rec))
    summary.append({k: rec[k] for k in ("station", "metro", "days", "volume", "packages_total")} |
                   {"sortable_share": env_share, "pts_per_5cm": rec["envelope"]["pts_per_5cm_at_default"],
                    "max_zone_prefixes": max_prefix, **{k: v for k, v in rec["sizing"].items() if k != "des_curve"},
                    "peak_rate_over_mean_rate": rec["design_day"]["peak_15min_rate_per_h"] / lam})
    print(s, len(days), "routes", design_routes, "prefix", max_prefix, "peak/mean rate %.2f" % (rec["design_day"]["peak_15min_rate_per_h"]/lam), round(mean), round(p90), f"env {env_share:.3f}", "cells hand/mean/erl/des/dest", c_hand, c_hand_mean, c_erl, c_des, rec["sizing"]["cells_for_destinations"])

allsd = dims
summary_doc = {"stations": summary, "assumptions": {k: getattr(C, k) for k in dir(C) if k.isupper()},
               "dataset": {"name": "Amazon Last Mile Routing Research Challenge 2021 (training split)",
                           "url": "https://registry.opendata.aws/amazon-last-mile-challenges/", "licence": "CC BY-NC 4.0",
                           "routes": len(R), "packages": int(len(dims)), "stations": int(len(set(station))),
                           "dates": [min(date), max(date)], "reconciliation": meta["reconciliation"],
                           "all_sortable_share": share(allsd, **C.ENVELOPE)}}
(WEB / "summary.json").write_text(json.dumps(summary_doc, indent=1, default=float))
