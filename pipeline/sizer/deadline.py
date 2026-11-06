"""Deadline-aware lower bound on cells (processor-demand criterion).

For any interval [t1, t2], parcels that arrive at or after t1 and must be
sorted by t2 have to be processed inside that interval. With c cells at rate
mu, c * mu * (t2 - t1) >= N(t1, t2) for every interval, so

    c >= max over t1 < t2 of ceil( N(t1, t2) / (mu * (t2 - t1)) ).

This holds for ANY induction policy (FIFO, EDF, anything), so it is a floor.
N is the fluid expectation under the per-route uniform inbound assumption
(route r arrives uniformly on [D_r - open_h, D_r - close_h], due D_r - cutoff_h).
"""
from __future__ import annotations

import math

import numpy as np


def demand_ratio(departures_s, counts, open_h, close_h, cutoff_h, mu_h, grid_s=300.0, slack=0.0):
    """Return (max N/(mu*dt), t1, t2) over t1 on a grid plus every route's arrival
    start, and t2 at every route's cutoff (demand only steps at cutoffs)."""
    d = np.asarray(departures_s, float); n = np.asarray(counts, float)
    a, b, k = d - open_h * 3600, d - close_h * 3600, d - cutoff_h * 3600
    t1s = np.unique(np.concatenate([np.arange(a.min(), k.max(), grid_s), a, b]))
    t2s = np.unique(k)
    best = (0.0, None, None)
    for t2 in t2s:
        due = k <= t2
        t1 = t1s[t1s < t2][:, None]
        frac = np.clip((b[due] - np.maximum(t1, a[due])) / (b[due] - a[due]), 0.0, 1.0)
        N = np.maximum((frac * n[due]).sum(axis=1) - slack, 0.0)
        r = N / (mu_h / 3600.0 * (t2 - t1[:, 0]))
        j = int(np.argmax(r))
        if r[j] > best[0]:
            best = (float(r[j]), float(t1[j, 0]), float(t2))
    return best


def cells_deadline_bound(departures_s, counts, open_h, close_h, cutoff_h, mu_h, grid_s=300.0, slack=0.0) -> int:
    r, _, _ = demand_ratio(departures_s, counts, open_h, close_h, cutoff_h, mu_h, grid_s, slack)
    return max(1, math.ceil(r - 1e-9))
