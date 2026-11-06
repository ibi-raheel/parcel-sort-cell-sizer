import numpy as np
from sizer.sim import run, gamma_service, wave_arrivals, miss_curve
from sizer.validate import mmc_check


def test_des_matches_erlang_c():
    r = mmc_check(1400, 500, 4, n=120_000)
    assert abs(r["wq_sim_min"] - r["wq_theory_min"]) / r["wq_theory_min"] < 0.08
    assert abs(r["pwait_sim"] - r["pwait_theory"]) < 0.02


def test_littles_law_holds():
    r = mmc_check(1800, 500, 4, n=120_000)
    assert abs(r["littles_Lq"] - r["littles_lambdaW"]) / r["littles_lambdaW"] < 0.05


def test_deterministic_single_server_by_hand():
    a = np.array([0.0, 1.0, 2.0]); sv = np.array([3.0, 3.0, 3.0])
    s, f = run(a, sv, 1)
    assert s.tolist() == [0, 3, 6] and f.tolist() == [3, 6, 9]
    s, f = run(a, sv, 3)
    assert (s == a).all()


def test_gamma_service_mean_and_cv():
    x = gamma_service(np.random.default_rng(0), 200_000, 7.2, 0.25)
    assert abs(x.mean() - 7.2) < 0.02 and abs(x.std() / x.mean() - 0.25) < 0.01


def test_wave_arrivals_respect_window():
    rng = np.random.default_rng(1)
    deps = np.array([20000.0, 26000.0]); n = np.array([500, 300])
    a, ix = wave_arrivals(rng, deps, n, 3, 1)
    assert len(a) == 800 and (np.diff(a) >= 0).all()
    assert ((a >= deps[ix] - 3 * 3600) & (a <= deps[ix] - 3600)).all()


def test_more_cells_never_worse():
    rng = np.random.default_rng(2)
    c = miss_curve(rng, np.array([20000.0, 23000.0]), np.array([1500, 1500]), 0.5, 3, 1, 500, 0.25, [1, 2, 3, 4], reps=3)
    m = [p["miss_share"] for p in c]
    assert all(x >= y for x, y in zip(m, m[1:]))
