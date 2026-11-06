"""Step 7: P90 demand forecasting (quantile gradient boosting vs baselines) and its cell-count consequence.

Writes public/data/forecast.json. Reads the cached package table (SIZER_CACHE) and
the per-station results from analyse.py (exception share, six sized stations).
"""
import json, math, os, sys, time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sizer import config as C  # noqa: E402
from sizer.forecast import Panel, run_level, FEATURES  # noqa: E402
from sizer.sim import cells_needed, miss_curve  # noqa: E402

OUT = Path(os.environ.get("SIZER_CACHE", ROOT / "out"))
WEB = ROOT.parent / "public" / "data"
meta = json.loads((OUT / "routes.json").read_text())
z = np.load(OUT / "packages.npz")
R = meta["routes"]
n = np.bincount(z["route_i"], minlength=len(R))
S = json.loads((WEB / "summary.json").read_text())
SIX = [s["station"] for s in S["stations"]]
EXC = {s["station"]: 1 - s["sortable_share"] for s in S["stations"]}


def hms(s):
    h, m, x = map(int, s.split(":")); return h * 3600 + m * 60 + x


station = [r["station"] for r in R]
dates = sorted({r["date"] for r in R}); didx = {d: i for i, d in enumerate(dates)}
day = [didx[r["date"]] for r in R]
dep_s = np.array([hms(r["departure_utc"]) for r in R], float)
hour = [int((hms(r["departure_utc"]) // 3600 + C.UTC_OFFSET_H[r["station"][:3]]) % 24) for r in R]
cap = [r["capacity_cm3"] for r in R]
P = Panel(station, day, hour, cap, n, dates)
six_idx = {P.st_names.index(s) for s in SIX}
in_six = lambda U: np.isin(U["s"], list(six_idx))  # noqa: E731

t = time.time()
results = {}
for level in ("day", "wave", "route"):
    for h in (1, 7):
        r = run_level(P, level, h, seed=0)
        r6 = run_level(P, level, h, seed=0, eval_mask_fn=in_six)
        results[f"{level}_h{h}"] = r
        results[f"{level}_h{h}_six"] = r6
        sc = r["scores"]
        print(f"{level:5s} h={h} n={r['units']:5d} " + " | ".join(f"{k[:14]} PL {v['pinball']:.1f} cov {v['coverage']:.2f} f/y {v['forecast_over_actual']:.2f}" for k, v in sc.items()), flush=True)
        for k, b in r["model_vs"].items():
            print(f"     vs {k:26s} rel {b['rel_improvement']:+.3f} CI {np.round(b['rel_improvement_ci90'], 3)}  six: {r6['model_vs'][k]['rel_improvement']:+.3f} CI {np.round(r6['model_vs'][k]['rel_improvement_ci90'], 3)}", flush=True)
print(f"{time.time()-t:.0f}s", flush=True)

# ---- cell-count consequence: size each test station-day from each wave forecast, then run
# the same DES on the day's real per-route counts and record the late share.
W = dict(cutoff_h=C.CUTOFF_H, open_h=C.INBOUND_OPEN_H, close_h=C.INBOUND_CLOSE_H, rate_h=C.CELL_RATE_H, cv=C.SERVICE_CV)
st_arr = P.s; d_arr = P.d; h_arr = P.h
sizing = {}
for h in (1, 7):
    r6 = results[f"wave_h{h}_six"]; E = r6["_eval"]; U, ev, F = E["U"], E["mask"], E["f"]
    methods = list(F)
    rows = []
    for (s_i, d_i) in sorted({(int(a), int(b)) for a, b in zip(U["s"][ev], U["d"][ev])}):
        day_units = np.flatnonzero((U["s"] == s_i) & (U["d"] == d_i))
        if not ev[day_units].all():
            continue
        ridx = np.flatnonzero((st_arr == s_i) & (d_arr == d_i))
        deps = dep_s[ridx] - dep_s[ridx].min() + 4 * 3600
        e = EXC[P.st_names[s_i]]
        unit_of = {int(U["h"][u]): u for u in day_units}
        u_r = np.array([unit_of[int(h_arr[j])] for j in ridx])
        actual = np.round(n[ridx] * (1 - e)).astype(int)
        span = (deps.max() - deps.min()) / 3600 + (C.INBOUND_OPEN_H - C.INBOUND_CLOSE_H)
        seed = 1000 * s_i + d_i
        def size(counts):
            return cells_needed(np.random.default_rng(seed), deps, counts, c_start=max(1, math.ceil(counts.sum() / (span * C.CELL_RATE_H))), reps=2, **W)
        c_act = size(actual)
        row = {"station": P.st_names[s_i], "date": dates[d_i], "routes": int(len(ridx)), "packages": int(n[ridx].sum()), "cells_needed_actual": c_act}
        for m in methods:
            fr = F[m][u_r] / U["routes"][u_r]
            fc = np.round(fr * (1 - e)).astype(int)
            c_m = size(fc)
            late = miss_curve(np.random.default_rng(seed + 7), deps, actual, W["cutoff_h"], W["open_h"], W["close_h"], W["rate_h"], W["cv"], [c_m], reps=4)[0]
            row[m] = {"cells": int(c_m), "late_share": late["miss_share"], "routes_late_share": late["routes_late_share"]}
        rows.append(row)
    summ = {}
    for m in methods:
        c = np.array([r[m]["cells"] for r in rows]); ca = np.array([r["cells_needed_actual"] for r in rows])
        late = np.array([r[m]["late_share"] for r in rows])
        summ[m] = {"cell_days": int(c.sum()), "cell_days_needed": int(ca.sum()), "under_days_share": float((late >= C.MISS_TARGET).mean()),
                   "under_cells": int(np.clip(ca - c, 0, None).sum()), "excess_cells": int(np.clip(c - ca, 0, None).sum()),
                   "exact_days_share": float((c == ca).mean()), "mean_late_share": float(late.mean()), "max_late_share": float(late.max()),
                   "abs_cell_error": int(np.abs(c - ca).sum())}
    # paired block bootstrap over dates: model minus each baseline in absolute cell error and in under-provisioned days
    from sizer.forecast import block_bootstrap_diff  # noqa: E402
    blocks = np.array([r["date"] for r in rows])
    ca = np.array([r["cells_needed_actual"] for r in rows])
    err = {m: np.abs(np.array([r[m]["cells"] for r in rows]) - ca).astype(float) for m in methods}
    und = {m: (np.array([r[m]["late_share"] for r in rows]) >= C.MISS_TARGET).astype(float) for m in methods}
    comp = {m: {"abs_cell_error": block_bootstrap_diff(err["model"], err[m], blocks, seed=3),
                "under_days": block_bootstrap_diff(und["model"], und[m], blocks, seed=3)} for m in methods if m != "model"}
    sizing[f"h{h}"] = {"station_days": len(rows), "summary": summ, "model_vs": comp, "rows": rows}
    print(f"h={h} station-days {len(rows)}", flush=True)
    for m, v in summ.items():
        print(f"   {m:30s} cells {v['cell_days']} (need {v['cell_days_needed']}) under-days {v['under_days_share']:.2f} excess {v['excess_cells']} short {v['under_cells']} exact {v['exact_days_share']:.2f} meanlate {v['mean_late_share']:.4f} maxlate {v['max_late_share']:.3f}", flush=True)

def clean(r):
    return {k: v for k, v in r.items() if k != "_eval"}
doc = {"quantile": 0.9, "features": FEATURES, "model": "HistGradientBoostingRegressor(loss='quantile', q=0.9) on packages per route, x planned routes",
       "validation": "rolling origin, test blocks of 5 consecutive dates from the 15th date, train on units dated <= first test date - h; units need >= 3 observed history days",
       "levels": {k: clean(v) for k, v in results.items()}, "sizing": sizing,
       "stations_in_training": P.st_names, "sized_stations": SIX}
(WEB / "forecast.json").write_text(json.dumps(doc, default=float, allow_nan=False))
print(f"done {time.time()-t:.0f}s")
for h in ("h1", "h7"):
    sz = sizing[h]
    for m, c in sz["model_vs"].items():
        e = c["abs_cell_error"]
        print(h, f"model vs {m:30s} abs cell error/day diff {e['mean_diff']:+.3f} CI {np.round(e['mean_diff_ci90'], 3)} P(better) {e['p_a_better']:.3f}")
    by = {}
    for r in sz["rows"]:
        b = by.setdefault(r["station"], [0, 0, 0, 0])
        b[0] += 1; b[1] += r["cells_needed_actual"]; b[2] += r["model"]["cells"]; b[3] += r["routes_x_ppr_calibrated"]["cells"]
    print(h, "station: days, cells needed, model, routes x ppr", by)
