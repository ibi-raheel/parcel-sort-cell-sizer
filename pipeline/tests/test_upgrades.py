import json
from pathlib import Path

import numpy as np
import pytest

from sizer.business import labour_case
from sizer.deadline import cells_deadline_bound, demand_ratio
from sizer.robust import bootstrap_design, bootstrap_design_days, coverage_diagnostics
from sizer.sim import run, run_priority, miss_curve, gamma_service

DATA = Path(__file__).resolve().parents[2] / "public" / "data"


# ---- EDF vs FIFO --------------------------------------------------------------
def test_priority_with_arrival_key_reproduces_fifo():
    rng = np.random.default_rng(3)
    a = np.sort(rng.uniform(0, 3600, 4000)); sv = gamma_service(rng, 4000, 7.2, 0.25)
    for c in (1, 2, 3, 5):
        s1, f1 = run(a, sv, c)
        s2, f2 = run_priority(a, sv, np.arange(len(a)), c)
        assert np.allclose(s1, s2) and np.allclose(f1, f2)


def test_edf_meets_deadlines_fifo_misses_hand_trace():
    # 2 servers, unit service. Four parcels at t=0 due at 10; one at t=0.5 due at 2.
    # FIFO: [0,1] p0 p1, [1,2] p2 p3, [2,3] p4 -> p4 finishes at 3 > 2 (late).
    # EDF:  [0,1] p0 p1, [1,2] p4 p2 (p4 has the earliest cutoff), [2,3] p3 -> all on time.
    a = np.array([0, 0, 0, 0, 0.5]); sv = np.ones(5); cut = np.array([10, 10, 10, 10, 2.0])
    _, ff = run(a, sv, 2)
    _, fe = run_priority(a, sv, cut, 2)
    assert ff.tolist() == [1, 1, 2, 2, 3] and (ff > cut).sum() == 1
    assert fe.tolist() == [1, 1, 2, 3, 2] and (fe > cut).sum() == 0


def test_edf_never_worse_than_fifo_on_a_wave():
    deps = np.array([20000.0, 21000.0, 26000.0]); n = np.array([1200, 1200, 1500])
    kw = dict(cutoff_h=0.5, open_h=3, close_h=1, rate_h=500, cv=0.25, c_values=[2, 3], reps=4)
    f = miss_curve(np.random.default_rng(5), deps, n, **kw, policy="fifo")
    e = miss_curve(np.random.default_rng(5), deps, n, **kw, policy="edf")
    for x, y in zip(f, e):
        assert y["miss_share"] <= x["miss_share"] + 1e-3 and x["miss_ci95"] is not None


# ---- deadline bound -----------------------------------------------------------
def test_deadline_bound_hand_calc():
    # One route, 1000 parcels arriving uniformly on [d-3h, d-1h], due d-0.5h, mu=500/h.
    # Over [t1, d-0.5h] with t1 = d-1h-x: N/(mu dt) = 500x/(500(x+0.5)), max at x=2h: 0.8.
    d = 20000.0
    r, t1, t2 = demand_ratio([d], [1000], 3, 1, 0.5, 500)
    assert r == pytest.approx(0.8) and t1 == pytest.approx(d - 3 * 3600) and t2 == pytest.approx(d - 1800)
    assert cells_deadline_bound([d], [1000], 3, 1, 0.5, 500) == 1
    assert cells_deadline_bound([d, d], [1500, 1500], 3, 1, 0.5, 500) == 3  # 2.4 -> 3
    # allowing 300 late parcels: (3000 - 300) / 1250 = 2.16 -> 3; allowing 600: 1.92 -> 2
    assert cells_deadline_bound([d, d], [1500, 1500], 3, 1, 0.5, 500, slack=300) == 3
    assert cells_deadline_bound([d, d], [1500, 1500], 3, 1, 0.5, 500, slack=600) == 2


def test_deadline_bound_is_at_least_hand_rule_and_floors_sim():
    rng = np.random.default_rng(9)
    deps = np.sort(rng.uniform(4 * 3600, 7 * 3600, 30)); n = rng.integers(150, 300, 30)
    b = cells_deadline_bound(deps, n, 3, 1, 0.5, 500)
    span = (deps.max() - deps.min()) / 3600 + 2
    assert b >= np.ceil(n.sum() / ((span + 0.5) * 500))  # [first arrival, last cutoff] is one of the windows
    # zero-late is impossible below the floor, under either policy
    cv = miss_curve(np.random.default_rng(1), deps, n, 0.5, 3, 1, 500, 0.0, [b - 1], reps=2, policy="edf")
    assert cv[0]["miss_share"] > 0


# ---- coverage + bootstrap -----------------------------------------------------
def test_coverage_diagnostic_flags_route_driven_volume():
    R = np.array([5, 10, 20, 40, 41, 39]); V = R * 220 + np.array([3, -2, 5, -4, 1, 0])
    d = coverage_diagnostics(R, V)
    assert d["corr_packages_routes"] > 0.999 and d["packages_per_route_cv"] < 0.05
    assert d["p90_over_mean_packages"] > d["p90_over_mean_packages_well_covered_days"]


def test_bootstrap_intervals_cover_point_estimate():
    rng = np.random.default_rng(0)
    R = rng.integers(20, 50, 30); counts = [rng.poisson(200, r) for r in R]
    b = bootstrap_design(R, counts, n_boot=500)
    lo, hi = b["packages_per_route_ci90"]; assert lo < b["packages_per_route"] < hi
    lo, hi = b["design_routes_ci90"]; assert lo <= b["design_routes"] <= hi


def test_bootstrap_days_use_real_departure_sets():
    R = np.array([3, 5, 8]); deps = [np.arange(r) * 600.0 for r in R]; cnt = [np.full(r, 100 + r) for r in R]
    for dd, cc in bootstrap_design_days(np.random.default_rng(1), R, deps, cnt, n_days=20):
        assert any(dd is x for x in deps) and len(cc) == len(dd) and set(cc) <= {103, 105, 108}


def test_coverage_correlation_is_reported_for_every_station():
    s = json.loads((DATA / "summary.json").read_text())
    for st in s["stations"]:
        c = st["coverage"]
        assert -1 <= c["corr_packages_routes"] <= 1 and c["packages_per_route_cv"] > 0
        assert st["cells_bound_1pct"] <= st["cells_edf20"] <= st["cells_fifo20"]


# ---- business -----------------------------------------------------------------
def test_labour_case_hand_calc():
    # 40 manual heads vs 7 cells x 1 operator + 2 exception heads = 9; 31 x 18.10 x 5 h x 300 d
    r = labour_case(40, 7, 1, 2, 18.10, 5.0, 300)
    assert r["annual_labour_delta_usd"] == pytest.approx(31 * 18.10 * 5 * 300)
    assert r["breakeven_capex_per_cell_usd"]["24"] == pytest.approx(31 * 18.10 * 5 * 300 * 2 / 7)
