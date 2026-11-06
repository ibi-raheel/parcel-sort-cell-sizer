"""Sample-coverage diagnostics and day-block bootstrap for the design day.

The public sample holds a varying subset of each station's routes per day, so
daily package totals mostly measure how many routes were sampled. The design
day is therefore built as routes x packages-per-route, and its uncertainty is
taken from a bootstrap that resamples whole days (a day is the block).
"""
from __future__ import annotations

import numpy as np


def coverage_diagnostics(day_routes: np.ndarray, day_packages: np.ndarray) -> dict:
    """How much of daily volume is explained by the number of sampled routes."""
    R = np.asarray(day_routes, float); V = np.asarray(day_packages, float)
    ppr = V / R
    full = R >= 0.5 * R.max()  # days with at least half the busiest day's route coverage
    def p90m(x):
        return float(np.percentile(x, 90) / x.mean())
    return {
        "corr_packages_routes": float(np.corrcoef(R, V)[0, 1]),
        "packages_per_route_mean": float(ppr.mean()),
        "packages_per_route_cv": float(ppr.std(ddof=1) / ppr.mean()),
        "routes_min": int(R.min()), "routes_max": int(R.max()),
        "packages_min": int(V.min()), "packages_max": int(V.max()),
        "p90_over_mean_packages": p90m(V),
        "p90_over_mean_packages_well_covered_days": p90m(V[full]),
        "well_covered_days": int(full.sum()),
        "p90_over_mean_packages_per_route": p90m(ppr),
    }


def bootstrap_design(day_routes, day_route_counts: list[np.ndarray], n_boot=2000, seed=0, q=90) -> dict:
    """Day-block bootstrap: 90% intervals for pooled packages-per-route and for the P90 route count."""
    rng = np.random.default_rng(seed)
    R = np.asarray(day_routes, float)
    tot = np.array([c.sum() for c in day_route_counts], float)
    m = len(R)
    idx = rng.integers(0, m, size=(n_boot, m))
    ppr = tot[idx].sum(1) / R[idx].sum(1)
    rq = np.percentile(R[idx], q, axis=1)
    return {"packages_per_route": float(tot.sum() / R.sum()),
            "packages_per_route_ci90": np.percentile(ppr, [5, 95]).tolist(),
            "design_routes": float(np.percentile(R, q)),
            "design_routes_ci90": np.percentile(rq, [5, 95]).tolist(), "n_boot": n_boot}


def bootstrap_design_days(rng, day_routes, day_deps: list[np.ndarray], day_route_counts: list[np.ndarray], n_days=200, q=90):
    """Yield (departures_s, counts) for bootstrap design days.

    Each replicate resamples the observed days, takes the P90 route count R_b of
    that resample, uses the real departure set of an observed day whose route
    count is closest to R_b, and draws that many real per-route package counts
    from the routes on the resampled days.
    """
    R = np.asarray(day_routes)
    m = len(R)
    for _ in range(n_days):
        idx = rng.integers(0, m, m)
        Rb = np.percentile(R[idx], q)
        gap = np.abs(R - Rb)
        cand = np.flatnonzero(gap == gap.min())
        j = int(rng.choice(cand))
        deps = day_deps[j]
        pool = np.concatenate([day_route_counts[i] for i in idx])
        yield deps, rng.choice(pool, size=len(deps), replace=True)
