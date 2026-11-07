"""size-site CLI: reproduces the shipped DLA7 results, and a CSV export maps onto the same table."""
import csv, importlib.util, json, os
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parent / "public" / "data"
CACHE = Path(os.environ.get("SIZER_CACHE", Path.home() / "Developer/job-hunt-builds/_downloads/almrrc/derived"))
spec = importlib.util.spec_from_file_location("size_site", ROOT / "scripts" / "size_site.py")
size_site = importlib.util.module_from_spec(spec); spec.loader.exec_module(size_site)
needs_cache = pytest.mark.skipif(not (CACHE / "packages.npz").exists(), reason="pipeline cache not built (run run_all.sh)")


@needs_cache
def test_dla7_reproduces_summary(tmp_path):
    res = size_site.main(["--station", "DLA7", "--cache", str(CACHE), "--out", str(tmp_path)])
    S = next(s for s in json.loads((DATA / "summary.json").read_text())["stations"] if s["station"] == "DLA7")
    L = res["ladder"]
    assert (L["floor"], L["edf"], L["fifo"], L["p90_of_peak_days"]) == (S["cells_bound_1pct"], S["cells_edf20"], S["cells_fifo20"], S["cells_90pct_confidence"]) == (6, 6, 7, 8)
    assert L["average_throughput_rule"] == S["cells_hand_mean"] == 5        # the average rule is a cell short of FIFO
    assert res["one_cell_short"]["late_share"] == pytest.approx(S["one_cell_short"]["late_share"]) == pytest.approx(0.0672, abs=1e-4)
    be = {(c["manual_rate_h"], c["ops_per_cell"]): c["24mo"] for c in res["breakeven_capex_per_cell"]}
    assert round(be[(275, 1)]) == 34907 and round(be[(275, 0.5)]) == 59342
    assert res["measure_first"][0]["param"] == "rate_h"                       # cell rate is the first thing to measure
    md = (tmp_path / "size-site-DLA7.md").read_text()
    assert "Earliest cutoff first | 6" in md and "6.7% of parcels late" in md


@needs_cache
def test_csv_export_of_real_routes_maps_to_same_daily_volumes(tmp_path):
    T = size_site.subset(size_site.load_cache(CACHE), "DLA7", None, None)
    pk = np.bincount(T["ri"], minlength=len(T["R"]))
    p = tmp_path / "site.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["route_id", "date", "departure_local", "packages"])
        for i, (r, n) in enumerate(zip(T["R"], pk)):
            w.writerow([f"r{i}", r["date"], r["departure_utc"], int(n)])
    C = size_site.subset(size_site.load_csv(p, "SITE"), "SITE", None, None)
    cpk = np.bincount(C["ri"], minlength=len(C["R"]))
    daily = {}
    for r, n in zip(C["R"], cpk):
        daily[r["date"]] = daily.get(r["date"], 0) + int(n)
    shipped = {d["date"]: d["packages"] for d in json.loads((DATA / "station-DLA7.json").read_text())["daily"]}
    assert daily == shipped
    assert len(set(C["zi"].tolist())) == len(C["R"])                          # one destination per route
    assert (C["dims"] == 0).all() and len(C["dims"]) == sum(shipped.values())  # no dims given: all fit
