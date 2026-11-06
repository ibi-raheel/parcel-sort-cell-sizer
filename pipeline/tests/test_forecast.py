import json
from pathlib import Path

import numpy as np
import pytest

from sizer.forecast import (FEATURES, Panel, baseline_last_week, baseline_trailing_mean, block_bootstrap_diff,
                            pinball, rolling_folds, run_level, scores)

DATA = Path(__file__).resolve().parents[2] / "public" / "data"
DATES = [f"2018-07-{d:02d}" for d in range(1, 31)]   # 2018-07-01 is a Sunday


def toy_panel(n_by_day, hour=8, cap=3e6):
    """One station, one route per listed (day, count) pair."""
    st, day, hr, cp, n = [], [], [], [], []
    for d, counts in n_by_day.items():
        for c in counts:
            st.append("S1"); day.append(d); hr.append(hour); cp.append(cap); n.append(c)
    return Panel(st, day, hr, cp, n, DATES[: max(n_by_day) + 1])


# ---- hand-checkable -------------------------------------------------------------
def test_pinball_by_hand():
    # q = 0.9. y=10, f=12: over-forecast by 2 -> (1-0.9)*2 = 0.2. y=20, f=15: under by 5 -> 0.9*5 = 4.5.
    loss = pinball([10, 20], [12, 15], 0.9)
    assert loss.tolist() == pytest.approx([0.2, 4.5])
    s = scores([10, 20], [12, 15])
    assert s["pinball"] == pytest.approx(2.35) and s["coverage"] == 0.5
    assert s["forecast_over_actual"] == pytest.approx(27 / 30) and s["mean_shortfall_when_under"] == pytest.approx(5)


def test_naive_baselines_by_hand():
    # one route a day; day d carries 100 + 10 d packages, days 0..9
    P = toy_panel({d: [100 + 10 * d] for d in range(10)})
    U = P.units("day")
    i9 = int(np.flatnonzero(U["d"] == 9)[0])
    # h = 1: origin = day 8, window days 2..8 -> mean(120..180) = 150, x 1.3 = 195
    assert baseline_trailing_mean(P, U, 1, "day")[i9] == pytest.approx(195.0)
    # same weekday last week = day 2 = 120
    f, fb = baseline_last_week(P, U, 1, "day")
    assert f[i9] == 120 and not fb[i9]
    # h = 7: origin = day 2, window days 0..2 -> mean(100, 110, 120) = 110 x 1.3; day 2 is still <= origin
    assert baseline_trailing_mean(P, U, 7, "day")[i9] == pytest.approx(143.0)
    # h = 8: day 2 is after the origin, D-14 does not exist -> falls back to the unscaled trailing mean (days 0..1)
    f8, fb8 = baseline_last_week(P, U, 8, "day")
    assert fb8[i9] and f8[i9] == pytest.approx(105.0)


def test_features_by_hand():
    # two routes a day with 200 and 220 packages (ppr 210), day 5 has 3 routes -> routes_ratio 1.5
    P = toy_panel({0: [200, 220], 1: [200, 220], 2: [200, 220], 3: [200, 220], 4: [200, 220], 5: [200, 220, 240]})
    U = P.units("day")
    X = P.features(U, 1)
    c = {f: i for i, f in enumerate(FEATURES)}
    row = X[int(np.flatnonzero(U["d"] == 5)[0])]
    assert row[c["routes"]] == 3 and row[c["ppr7"]] == pytest.approx(210) and row[c["ppr_last"]] == pytest.approx(210)
    assert row[c["routes_ratio"]] == pytest.approx(1.5) and np.isnan(row[c["ppr_dow"]])  # no same weekday before


# ---- leakage --------------------------------------------------------------------
@pytest.mark.parametrize("h", [1, 7])
def test_features_ignore_everything_after_the_origin(h):
    rng = np.random.default_rng(0)
    base = {d: list(rng.integers(150, 300, 4)) for d in range(20)}
    D = 15
    changed = {d: (v if d <= D - h else [9999] * len(v)) for d, v in base.items()}
    P1, P2 = toy_panel(base), toy_panel(changed)
    U1, U2 = P1.units("wave"), P2.units("wave")
    i1 = np.flatnonzero(U1["d"] == D); i2 = np.flatnonzero(U2["d"] == D)
    X1, X2 = P1.features(U1, h)[i1], P2.features(U2, h)[i2]
    assert np.allclose(X1, X2, equal_nan=True)
    assert np.allclose(baseline_trailing_mean(P1, U1, h, "wave")[i1], baseline_trailing_mean(P2, U2, h, "wave")[i2])


def test_rolling_folds_are_consecutive_and_cover():
    f = rolling_folds(np.arange(39), 14, 5)
    assert f[0] == (14, 18) and f[-1] == (34, 38)
    assert all(b[0] == a[1] + 1 for a, b in zip(f, f[1:]))


def test_block_bootstrap_by_hand():
    # two dates; model better by 1 on every unit -> mean diff exactly -1, CI collapses to -1
    a = np.array([1.0, 1, 2, 2]); b = a + 1; blocks = np.array([0, 0, 1, 1])
    r = block_bootstrap_diff(a, b, blocks, n_boot=200)
    assert r["mean_diff"] == -1 and r["mean_diff_ci90"] == [-1, -1] and r["p_a_better"] == 1
    assert r["rel_improvement"] == pytest.approx(1 - 6 / 10)


# ---- the model learns structure a flat rule cannot (synthetic fixture, test only) --
def test_quantile_model_learns_hour_effect_and_heteroscedasticity():
    rng = np.random.default_rng(1)
    st, day, hr, cp, n = [], [], [], [], []
    for s in ("A", "B", "C"):
        for d in range(30):
            for hour, ppr in ((6, 180), (8, 260)):
                for _ in range(rng.integers(1, 8)):
                    st.append(s); day.append(d); hr.append(hour); cp.append(3e6); n.append(rng.normal(ppr, 15))
    P = Panel(st, day, hr, cp, n, DATES)
    r = run_level(P, "wave", 1)
    m = r["scores"]["model"]
    assert 0.7 <= m["coverage"] <= 0.98   # ~96 test units, so coverage is noisy around 0.9
    assert m["pinball"] < r["scores"]["routes_x_ppr_calibrated"]["pinball"]
    assert m["pinball"] < r["scores"]["trailing_mean_x1.3"]["pinball"]


# ---- exported results -------------------------------------------------------------
def test_exported_forecast_is_consistent():
    p = DATA / "forecast.json"
    if not p.exists():
        pytest.skip("run scripts/forecast.py first")
    F = json.loads(p.read_text())
    for k, lv in F["levels"].items():
        assert lv["units"] > 0
        for s in lv["scores"].values():
            assert 0 <= s["coverage"] <= 1 and s["pinball"] >= 0
        for b in lv["model_vs"].values():
            if b["rel_improvement_ci90"] is None:
                continue
            lo, hi = b["rel_improvement_ci90"]
            assert lo <= b["rel_improvement"] + 1e-9 and b["rel_improvement"] <= hi + 1e-9 or b["n_blocks"] < 3
    for h, sz in F["sizing"].items():
        for row in sz["rows"]:
            assert row["cells_needed_actual"] >= 1
