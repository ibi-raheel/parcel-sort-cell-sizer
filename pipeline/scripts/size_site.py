"""size-site: run the cell-sizing recipe (SOLUTION.md) on one station's route history.

  python -I scripts/size_site.py --station DLA7                                   # pipeline cache (fast)
  python -I scripts/size_site.py --routes route_data.json --packages package_data.json --station DLA7
  python -I scripts/size_site.py --csv site_routes.csv --station SITE

CSV columns: route_id, date (YYYY-MM-DD), departure_local (HH:MM[:SS]), packages[, L, W, H in cm].
Rows with the same route_id and date are summed, so a per-route or a per-parcel export both work;
L/W/H, when given, apply to every parcel on that row.

Writes out/size-site-<station>.json and out/size-site-<station>.md. No modelling lives here: the
sizing is sizer/site.py::size_station(), the same code that produced public/data/.
"""
import argparse, csv, json, os, sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sizer import config as C  # noqa: E402
from sizer.forecast import Q, SIZE_EDGES  # noqa: E402
from sizer.site import hms, size_station  # noqa: E402

BUCKETS = ["1 route", "2-3 routes", "4-6 routes", "7+ routes"]
SHIPPED = ROOT.parent / "public" / "data" / "forecast.json"


def load_cache(d: Path) -> dict:
    meta = json.loads((d / "routes.json").read_text()); z = np.load(d / "packages.npz")
    return {"R": meta["routes"], "ri": z["route_i"], "zi": z["zone_i"], "dims": z["dims"], "zone_names": meta["zone_names"]}


def load_json(routes: Path, packages: Path) -> dict:
    from sizer.ingest import build_table
    T = build_table(packages, routes)
    R = [{k: v for k, v in T["routes"][r].items() if k != "zones"} for r in T["route_ids"]]
    return {"R": R, "ri": T["route_i"], "zi": T["zone_i"], "dims": T["dims"], "zone_names": T["zone_names"]}


def load_csv(path: Path, station: str) -> dict:
    keys, R, ri, dims = {}, [], [], []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            k = (row["route_id"].strip(), row["date"].strip())
            if k not in keys:
                t = row["departure_local"].strip()
                keys[k] = len(R)
                R.append({"station": station, "date": k[1], "departure_utc": t if t.count(":") == 2 else t + ":00", "local": True})
            n = int(float(row["packages"]))
            ri += [keys[k]] * n
            lwh = [row.get(c, "") or "" for c in ("L", "W", "H")]
            dims += [sorted((float(x) for x in lwh), reverse=True) if all(lwh) else [0.0, 0.0, 0.0]] * n
    # one destination (gaylord) per route: the route itself is the zone
    return {"R": R, "ri": np.asarray(ri, np.int32), "zi": np.asarray(ri, np.int32), "dims": np.asarray(dims, np.float32),
            "zone_names": [f"{a}.{b}" for a, b in keys]}


def subset(T: dict, station: str, lo: str | None, hi: str | None) -> dict:
    keep = np.array([r["station"] == station and (lo is None or r["date"] >= lo) and (hi is None or r["date"] <= hi) for r in T["R"]])
    if not keep.any():
        sys.exit(f"no routes for station {station} in the date range")
    new = np.full(len(keep), -1); new[keep] = np.arange(keep.sum())
    pm = keep[T["ri"]]
    return {"R": [r for r, k in zip(T["R"], keep) if k], "ri": new[T["ri"][pm]].astype(np.int32), "zi": T["zi"][pm],
            "dims": T["dims"][pm], "zone_names": T["zone_names"]}


def local_hour(r: dict) -> int:
    off = 0 if r.get("local") else C.UTC_OFFSET_H.get(r["station"][:3], 0)
    return (hms(r["departure_utc"]) // 3600 + off) % 24


def wave_margins(R, pk, n_days: int) -> tuple[dict, str]:
    """Per-wave-size P90 multiplier on routes x trailing-7-day parcels per route (the size-aware rule).

    14+ days of history: refit on this site (in-sample, one q90 per bucket, pooled k for a bucket with
    under 20 waves). Otherwise: the multipliers fitted on the public data (last 1-day-ahead fold).
    """
    if n_days < 14:
        f = json.loads(SHIPPED.read_text())["levels"]["wave_h1"]["folds"][-1]
        return {int(b): v for b, v in f["calibration_k_by_wave_size"].items()}, "shipped (fitted on public data; under 14 days of site history)"
    days = sorted({r["date"] for r in R}); di = {d: i for i, d in enumerate(days)}
    Y, N = np.zeros(len(days)), np.zeros(len(days))
    waves = {}
    for r, n in zip(R, pk):
        d = di[r["date"]]; Y[d] += n; N[d] += 1
        w = waves.setdefault((d, local_hour(r)), [0, 0]); w[0] += 1; w[1] += n
    ratio, bucket = [], []
    for (d, _), (routes, y) in waves.items():
        if d < 3:
            continue
        lo = max(0, d - 7)
        ppr = Y[lo:d].sum() / N[lo:d].sum()
        ratio.append(y / (routes * ppr)); bucket.append(int(np.digitize(routes, SIZE_EDGES)))
    ratio, bucket = np.array(ratio), np.array(bucket)
    k = float(np.quantile(ratio, Q))
    return {b: float(np.quantile(ratio[bucket == b], Q)) if (bucket == b).sum() >= 20 else k for b in range(4)}, f"refit on {len(days)} days of this site's history (in-sample)"


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--station", required=True)
    src = a.add_mutually_exclusive_group()
    src.add_argument("--cache", type=Path, default=Path(os.environ.get("SIZER_CACHE", Path.home() / "Developer/job-hunt-builds/_downloads/almrrc/derived")))
    src.add_argument("--csv", type=Path)
    src.add_argument("--routes", type=Path)
    a.add_argument("--packages", type=Path)
    a.add_argument("--from", dest="lo"); a.add_argument("--to", dest="hi")
    a.add_argument("--cell-rate", type=float, default=C.CELL_RATE_H)
    a.add_argument("--uplift", type=float, default=C.PEAK_UPLIFT)
    a.add_argument("--open", type=float, default=C.INBOUND_OPEN_H)
    a.add_argument("--close", type=float, default=C.INBOUND_CLOSE_H)
    a.add_argument("--cutoff", type=float, default=C.CUTOFF_H)
    a.add_argument("--gaylords", type=int, default=C.GAYLORDS_PER_CELL)
    a.add_argument("--ops", default=",".join(f"{x:g}" for x in C.OPS_PER_CELL))
    a.add_argument("--wage", type=float, default=C.WAGE_H)
    a.add_argument("--seed", type=int, default=20211)
    a.add_argument("--out", type=Path, default=ROOT / "out")
    x = a.parse_args(argv)

    if x.csv:
        T = load_csv(x.csv, x.station)
    elif x.routes:
        if not x.packages:
            a.error("--routes needs --packages")
        T = load_json(x.routes, x.packages)
    else:
        T = load_cache(x.cache)
    T = subset(T, x.station, x.lo, x.hi)
    P = SimpleNamespace(**{k: getattr(C, k) for k in dir(C) if k.isupper()})
    P.CELL_RATE_H, P.PEAK_UPLIFT, P.INBOUND_OPEN_H, P.INBOUND_CLOSE_H = x.cell_rate, x.uplift, x.open, x.close
    P.CUTOFF_H, P.GAYLORDS_PER_CELL, P.WAGE_H = x.cutoff, x.gaylords, x.wage
    P.OPS_PER_CELL = tuple(float(v) if "." in v else int(v) for v in x.ops.split(","))

    R = T["R"]; pk = np.bincount(T["ri"], minlength=len(R))
    st = np.array([r["station"] for r in R]); dt = np.array([r["date"] for r in R])
    rec, row = size_station(x.station, R, T["ri"], T["zi"], T["dims"], T["zone_names"], pk, st, dt, np.random.default_rng(x.seed), P)
    res = recommend(rec, row, R, pk, P)
    x.out.mkdir(parents=True, exist_ok=True)
    (x.out / f"size-site-{x.station}.json").write_text(json.dumps(res, indent=1, default=float))
    (x.out / f"size-site-{x.station}.md").write_text(render(res))
    print(f"wrote {x.out / f'size-site-{x.station}.md'}")
    return res


def rel_margin(t: dict) -> float:
    """How far an input can move before the count rises, relative to base (scripts/validate.py week-1 ranking)."""
    f = t["flip_up_at"]
    if f is None:
        return float("inf")
    return abs(f - t["base"]) / (1 + t["base"]) if t["param"] == "uplift" else abs(f - t["base"]) / t["base"]


def recommend(rec, row, R, pk, P) -> dict:
    cov, dd, sz, lad = rec["coverage"], rec["design_day"], rec["sizing"], rec["sizing"]["ladder"]
    k, k_src = wave_margins(R, pk, rec["days"])
    ppr = rec["design_basis"]["packages_per_route"]
    by_hour = {}
    for r, n in zip(R, pk):
        if r["date"] == dd["date"]:
            w = by_hour.setdefault(local_hour(r), [0, 0]); w[0] += 1; w[1] += int(n)
    waves = []
    for h in sorted(by_hour):
        routes, obs = by_hour[h]; b = int(np.digitize(routes, SIZE_EDGES))
        p90 = routes * ppr * k[b]
        waves.append({"hour": h, "routes": routes, "observed": obs, "margin": k[b], "p90": round(p90), "p90_peak": round(p90 * (1 + P.PEAK_UPLIFT))})
    tor = {t["param"]: t for t in rec["sensitivity"]["tornado"]}
    order = sorted(("rate_h", "uplift", "open_h", "close_h", "cutoff_h", "cv"), key=lambda p: rel_margin(tor[p]))
    return {
        "station": rec["station"], "days": rec["days"], "assumptions": {k_: getattr(P, k_) for k_ in ("CELL_RATE_H", "PEAK_UPLIFT", "INBOUND_OPEN_H", "INBOUND_CLOSE_H", "CUTOFF_H", "GAYLORDS_PER_CELL", "OPS_PER_CELL", "WAGE_H")},
        "data_check": {"corr_packages_routes": cov["corr_packages_routes"], "size_on_routes_x_ppr": cov["corr_packages_routes"] >= 0.9,
                       "packages_per_route": ppr, "design_routes": rec["design_basis"]["design_routes"], "envelope_share": rec["envelope"]["sortable_share"]},
        "wave_margins": {"source": k_src, "by_bucket": {BUCKETS[b]: v for b, v in k.items()}},
        "design_day": {"date": dd["date"], "routes": dd["routes"], "design_packages": dd["design_packages"], "peak_over_mean_rate": row["peak_rate_over_mean_rate"], "waves": waves},
        "ladder": {"average_day_rule": sz["cells_hand_mean"], "busy_day_rule": sz["cells_hand_p90"], "floor": lad["bound_1pct"], "edf": lad["edf"], "fifo": lad["fifo"],
                   "p90_of_peak_days": sz["bootstrap_days"]["cells_90pct_confidence"], "destinations": sz["cells_for_destinations"],
                   "recommended": max(lad["edf"], sz["cells_for_destinations"]), "recommended_fifo": max(lad["fifo"], sz["cells_for_destinations"]),
                   "destinations_bind": sz["cells_for_destinations"] > lad["edf"]},
        "one_cell_short": rec["business"]["one_cell_short"],
        "measure_first": [{"param": p, "base": tor[p]["base"], "flip_up_at": tor[p]["flip_up_at"], "rel_margin": rel_margin(tor[p])} for p in order],
        "breakeven_capex_per_cell": [{"manual_rate_h": c["manual_rate_h"], "ops_per_cell": c["ops_per_cell"], **{f"{m}mo": v for m, v in c["breakeven_capex_per_cell_usd"].items()}} for c in rec["business"]["cases"]],
    }


NAMES = {"rate_h": "Sustained cell rate (/h)", "uplift": "Peak uplift", "open_h": "Inbound starts (h before departure)",
         "close_h": "Inbound ends (h before departure)", "cutoff_h": "Cutoff buffer (h)", "cv": "Pick-time variability (CV)"}


def render(r: dict) -> str:
    d, L, s, A = r["data_check"], r["ladder"], r["one_cell_short"], r["assumptions"]
    out = [f"# Cell sizing: {r['station']}", "",
           f"{r['days']} days of route history. Cell rate {A['CELL_RATE_H']:g}/h, peak uplift {A['PEAK_UPLIFT']:.0%}, inbound {A['INBOUND_OPEN_H']:g} h to {A['INBOUND_CLOSE_H']:g} h before departure, "
           f"cutoff {A['CUTOFF_H'] * 60:.0f} min, {A['GAYLORDS_PER_CELL']} destinations per cell.", "",
           f"**Recommendation: {L['recommended']} cells with earliest-cutoff-first induction ({L['recommended_fifo']} first come, first served); "
           f"{L['p90_of_peak_days']} clear 90% of bootstrap peak days.**" + (f" Destinations bind before throughput: {L['edf']} cells clear the waves, but the routes need {L['destinations']} at {A['GAYLORDS_PER_CELL']} per cell." if L["destinations_bind"] else ""), "",
           "## 1. Data check",
           f"- Daily volume vs routes: correlation {d['corr_packages_routes']:.3f}. " + ("Size on routes x parcels per route." if d["size_on_routes_x_ppr"] else "Volume does not track routes; size on daily totals and check for missing days."),
           f"- Parcels per route {d['packages_per_route']:.1f}; P90 route count {d['design_routes']:.0f}; {d['envelope_share']:.1%} of parcels fit the pick envelope.", "",
           f"## 2. Design-day P90 by wave ({r['design_day']['date']})",
           f"Margins: {r['wave_margins']['source']}. " + ", ".join(f"{b} x{v:.3f}" for b, v in r["wave_margins"]["by_bucket"].items()) + ".", "",
           "| Local hour | Routes | Observed | Margin | P90 | P90 at peak |", "|---|---|---|---|---|---|"]
    out += [f"| {w['hour']:02d}:00 | {w['routes']} | {w['observed']} | x{w['margin']:.3f} | {w['p90']} | {w['p90_peak']} |" for w in r["design_day"]["waves"]]
    out += ["", f"Peak 15-minute inbound is {r['design_day']['peak_over_mean_rate']:.2f}x the shift average.", "",
            "## 3. Cell ladder", "| Rule | Cells |", "|---|---|",
            f"| Average day (mean-day volume / sort window) | {L['average_day_rule']} |", f"| Busy-day hand rule (P90-day volume / sort window) | {L['busy_day_rule']} |",
            f"| Scheduling floor (<1% late, any policy) | {L['floor']} |", f"| Earliest cutoff first | {L['edf']} |", f"| First come, first served | {L['fifo']} |",
            f"| 90% of bootstrap peak days | {L['p90_of_peak_days']} |", f"| Destinations ({A['GAYLORDS_PER_CELL']} per cell) | {L['destinations']} |", ""]
    if s:
        out += [f"One cell short ({s['cells']} cells, first come first served): {s['late_share']:.1%} of parcels late, {s['routes_late_share']:.0%} of routes with a late parcel.", ""]
    out += ["## 4. Measure first on the site visit", "Shortest margin first: measure these in this order.", "", "| Input | Base | Count rises at | Margin |", "|---|---|---|---|"]
    out += [f"| {NAMES[m['param']]} | {m['base']:g} | {'never (in range searched)' if m['flip_up_at'] is None else format(round(m['flip_up_at'], 3), 'g')} | {'-' if m['flip_up_at'] is None else format(m['rel_margin'], '.0%')} |" for m in r["measure_first"]]
    out += ["", "## 5. Break-even capex per cell (labour only, no vendor price)", "| Manual rate /h | Operators per cell | 18 mo | 24 mo | 36 mo |", "|---|---|---|---|---|"]
    out += [f"| {c['manual_rate_h']} | {c['ops_per_cell']:g} | ${c['18mo']:,.0f} | ${c['24mo']:,.0f} | ${c['36mo']:,.0f} |" for c in r["breakeven_capex_per_cell"]]
    out += ["", "Negative: labour savings alone never pay the cell back at that staffing. Before maintenance, software and other running costs.", ""]
    return "\n".join(out)


if __name__ == "__main__":
    main()
