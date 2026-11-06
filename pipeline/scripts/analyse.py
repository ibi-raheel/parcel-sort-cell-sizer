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
from sizer.sim import miss_curve, cells_needed  # noqa: E402
from sizer.deadline import demand_ratio  # noqa: E402
from sizer.robust import coverage_diagnostics, bootstrap_design, bootstrap_design_days  # noqa: E402
from sizer.business import labour_case  # noqa: E402

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
    day_ridx = [np.where(rmask & (date == d))[0] for d in days]
    day_routes = np.array([len(x) for x in day_ridx])
    day_counts = [pk_per_route[x] for x in day_ridx]
    def _deps(ix):
        d_ = np.array([hms(R[i]["departure_utc"]) for i in ix], float)
        return d_ - d_.min() + 4 * 3600  # shift: first departure at t = 4 h
    day_deps = [_deps(x) for x in day_ridx]
    diag = coverage_diagnostics(day_routes, vol)
    boot = bootstrap_design(day_routes, day_counts, n_boot=C.N_BOOT, seed=7)
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
    # design day = routes x packages/route: the observed day whose route count is closest
    # to the P90 route count R* (ties: packages closest to R* x pooled packages/route),
    # with its real departures and real per-route counts, scaled to the +10% peak
    r_star = boot["design_routes"]
    key = np.abs(day_routes - r_star) * 1e6 + np.abs(vol - r_star * boot["packages_per_route"])
    di = int(np.argmin(key)); dday = days[di]
    routes_d = day_ridx[di]
    deps = day_deps[di]
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
    W = dict(cutoff_h=C.CUTOFF_H, open_h=C.INBOUND_OPEN_H, close_h=C.INBOUND_CLOSE_H, rate_h=C.CELL_RATE_H, cv=C.SERVICE_CV)

    # --- deadline ladder: processor-demand floor, EDF and FIFO with 20 reps and 95% CIs
    ratio, bt1, bt2 = demand_ratio(deps, counts, C.INBOUND_OPEN_H, C.INBOUND_CLOSE_H, C.CUTOFF_H, C.CELL_RATE_H)
    c_bound = max(1, math.ceil(ratio - 1e-9))  # zero-late floor
    ratio1, b1t1, b1t2 = demand_ratio(deps, counts, C.INBOUND_OPEN_H, C.INBOUND_CLOSE_H, C.CUTOFF_H, C.CELL_RATE_H, slack=C.MISS_TARGET * counts.sum())
    c_bound1 = max(1, math.ceil(ratio1 - 1e-9))  # floor for the same <1%-late target the DES uses
    lad_c = list(range(max(1, min(c_bound, c_bound1) - 1), c_des + 2))
    lad = {pol: miss_curve(np.random.default_rng(11), deps, counts, C.CUTOFF_H, C.INBOUND_OPEN_H, C.INBOUND_CLOSE_H,
                           C.CELL_RATE_H, C.SERVICE_CV, lad_c, reps=C.REPS_LADDER, policy=pol) for pol in ("fifo", "edf")}
    c_fifo20 = next((p["cells"] for p in lad["fifo"] if p["miss_share"] < C.MISS_TARGET), None)
    c_edf20 = next((p["cells"] for p in lad["edf"] if p["miss_share"] < C.MISS_TARGET), None)
    ladder = {"bound": c_bound, "bound_1pct": c_bound1, "bound_1pct_ratio": ratio1, "bound_ratio": ratio, "bound_window_h": [(bt1 - deps.min()) / 3600, (bt2 - deps.min()) / 3600],
              "bound_window_note": "hours relative to the first departure", "fifo": c_fifo20, "edf": c_edf20,
              "edf_saves_cells": (c_fifo20 - c_edf20) if (c_fifo20 and c_edf20) else None, "curves": lad, "reps": C.REPS_LADDER}

    # --- bootstrap design days: P(c cells keep late parcels under 1%)
    brng = np.random.default_rng(23)
    need = []
    for bdeps, bcnt in bootstrap_design_days(brng, day_routes, day_deps, day_counts, n_days=C.N_BOOT_DAYS):
        bc = np.round(bcnt * (1 + C.PEAK_UPLIFT) * (1 - exc)).astype(int)
        need.append(cells_needed(brng, bdeps, bc, c_start=c_des, reps=2, **W))
    need = np.array(need)
    p_ok = {int(c): float((need <= c).mean()) for c in range(int(need.min()), int(need.max()) + 1)}
    c90 = int(np.percentile(need, 90, method="higher"))
    bootd = {"n_days": C.N_BOOT_DAYS, "cells_needed_hist": {int(k): int(v) for k, v in zip(*np.unique(need, return_counts=True))},
             "p_ok": p_ok, "cells_90pct_confidence": c90}

    # --- sensitivity on the synthetic / published assumptions (common random numbers)
    base = dict(open_h=C.INBOUND_OPEN_H, close_h=C.INBOUND_CLOSE_H, cutoff_h=C.CUTOFF_H, rate_h=C.CELL_RATE_H, cv=C.SERVICE_CV, uplift=C.PEAK_UPLIFT)
    def c_of(**kw):
        P = {**base, **kw}
        cn = np.round(pk_per_route[routes_d] * (1 + P["uplift"]) * (1 - exc)).astype(int)
        return cells_needed(np.random.default_rng(31), deps, cn, P["cutoff_h"], P["open_h"], P["close_h"], P["rate_h"], P["cv"], c_start=c_des, reps=4)
    c_base = c_of()
    sweeps = {"open_h": [2, 3, 4], "close_h": [0.5, 1.0, 1.5], "cutoff_h": [0.25, 0.5, 0.75], "rate_h": [400, 450, 500], "cv": [0.1, 0.25, 0.5], "uplift": [0.0, 0.1, 0.2]}
    # adverse / favourable search ranges for the flip point (bisection on a monotone step function)
    ranges = {"open_h": (1.6, 6.0), "close_h": (0.55, 2.0), "cutoff_h": (0.95, 0.0), "rate_h": (250.0, 800.0), "cv": (1.0, 0.0), "uplift": (0.6, -0.3)}
    def flip(name, target_val):
        lo, hi = base[name], target_val
        if c_of(**{name: hi}) == c_base:
            return None
        for _ in range(8):
            mid = (lo + hi) / 2
            if c_of(**{name: mid}) == c_base:
                lo = mid
            else:
                hi = mid
        return round(hi, 3)
    tornado = []
    for name, vals in sweeps.items():
        adv, fav = ranges[name]
        tornado.append({"param": name, "base": base[name], "sweep": {str(v): c_of(**{name: v}) for v in vals},
                        "flip_up_at": flip(name, adv), "flip_down_at": flip(name, fav),
                        "range_searched": [adv, fav]})
    sens = {"cells_base": c_base, "reps": 4, "tornado": tornado}

    # --- labour case: manual sorters as servers under the same wave and the same 1%-late rule
    all_counts = np.round(pk_per_route[routes_d] * (1 + C.PEAK_UPLIFT)).astype(int)
    exc_counts = np.round(pk_per_route[routes_d] * (1 + C.PEAK_UPLIFT) * exc).astype(int)
    mrng = np.random.default_rng(41)
    man = {}
    for rate in (275.0, 300.0):
        Wm = {**W, "rate_h": rate}
        man[str(int(rate))] = {"manual_heads_all": cells_needed(mrng, deps, all_counts, c_start=math.ceil(all_counts.sum() / (span_h * rate)), reps=4, **Wm),
                               "manual_heads_exceptions": cells_needed(mrng, deps, exc_counts, c_start=max(1, math.ceil(exc_counts.sum() / (span_h * rate))), reps=4, **Wm)}
    paid_h = math.ceil(span_h * 2) / 2
    cases = []
    for rate, m in man.items():
        for ops in C.OPS_PER_CELL:
            cases.append({"manual_rate_h": int(rate), **labour_case(m["manual_heads_all"], c_des, ops, m["manual_heads_exceptions"], C.WAGE_H, paid_h, C.DAYS_PER_YEAR)})
    short = next(p for p in curve if p["cells"] == c_des - 1) if c_des and c_des > 1 else None
    one_short = None
    if short:
        late_n = short["miss_share"] * counts.sum()
        one_short = {"cells": c_des - 1, "late_parcels": round(late_n), "late_share": short["miss_share"], "routes_late_share": short["routes_late_share"],
                     "overflow_heads_at_least": math.ceil(late_n / (C.MANUAL_RATE_H * span_h))}
    business = {"paid_hours_per_day": paid_h, "days_per_year": C.DAYS_PER_YEAR, "wage_h": C.WAGE_H, "manual": man, "cases": cases, "one_cell_short": one_short,
                "cells": c_des}
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
        "daily_routes": day_routes.tolist(),
        "coverage": diag, "design_basis": boot,
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
                   "cells_des": c_des, "cells_for_destinations": math.ceil(design_routes / C.GAYLORDS_PER_CELL), "cells_for_zone_prefixes": math.ceil(max_prefix / C.GAYLORDS_PER_CELL), "des_curve": curve,
                   "ladder": ladder, "bootstrap_days": bootd},
        "sensitivity": sens, "business": business,
    }
    # sample of sorted dims for the interactive envelope (integer mm/10 -> cm, 6000 parcels)
    samp = rng.choice(np.where(pkg_mask)[0], size=min(6000, pkg_mask.sum()), replace=False)
    rec["envelope"]["sample_cm"] = np.round(dims[samp]).astype(int).tolist()
    rec["envelope"]["sample_share"] = share(dims[samp], **C.ENVELOPE)
    (WEB / f"station-{s}.json").write_text(json.dumps(rec))
    summary.append({k: rec[k] for k in ("station", "metro", "days", "volume", "packages_total")} |
                   {"sortable_share": env_share, "pts_per_5cm": rec["envelope"]["pts_per_5cm_at_default"],
                    "max_zone_prefixes": max_prefix, **{k: v for k, v in rec["sizing"].items() if k != "des_curve"},
                    "peak_rate_over_mean_rate": rec["design_day"]["peak_15min_rate_per_h"] / lam,
                    "coverage": diag, "design_routes": r_star, "design_basis": boot,
                    "cells_bound": c_bound, "cells_bound_1pct": c_bound1, "cells_fifo20": c_fifo20, "cells_edf20": c_edf20, "cells_90pct_confidence": c90,
                    "p_ok": p_ok, "tornado": [{k: t[k] for k in ("param", "base", "flip_up_at", "flip_down_at")} for t in tornado],
                    "one_cell_short": one_short, "labour_cases": cases})
    print(s, len(days), "routes", design_routes, "prefix", max_prefix, "peak/mean rate %.2f" % (rec["design_day"]["peak_15min_rate_per_h"]/lam), round(mean), round(p90), f"env {env_share:.3f}", "cells hand/mean/erl/des/dest", c_hand, c_hand_mean, c_erl, c_des, rec["sizing"]["cells_for_destinations"],
          "| corr %.3f pprCV %.3f" % (diag["corr_packages_routes"], diag["packages_per_route_cv"]), "bound/edf/fifo", c_bound, c_edf20, c_fifo20, "c90", c90, p_ok, flush=True)

allsd = dims
summary_doc = {"stations": summary, "assumptions": {k: getattr(C, k) for k in dir(C) if k.isupper()},
               "dataset": {"name": "Amazon Last Mile Routing Research Challenge 2021 (training split)",
                           "url": "https://registry.opendata.aws/amazon-last-mile-challenges/", "licence": "CC BY-NC 4.0",
                           "routes": len(R), "packages": int(len(dims)), "stations": int(len(set(station))),
                           "dates": [min(date), max(date)], "reconciliation": meta["reconciliation"],
                           "all_sortable_share": share(allsd, **C.ENVELOPE)}}
(WEB / "summary.json").write_text(json.dumps(summary_doc, indent=1, default=float))
