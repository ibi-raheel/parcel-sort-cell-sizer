"""Discrete-event simulation of a pooled bank of c sort cells (FIFO, shared infeed).

Each package has an arrival time and a cutoff (its route's departure minus a
staging buffer). A package misses if it leaves its cell after its cutoff.
Event logic: with FIFO and identical servers, each arrival in time order takes
the server that frees up first; that is exact for G/G/c FIFO.
"""
from __future__ import annotations

import heapq

import numpy as np


def run(arrivals: np.ndarray, service: np.ndarray, c: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (start, finish) times. arrivals must be sorted ascending."""
    free = [0.0] * c
    heapq.heapify(free)
    start = np.empty_like(arrivals)
    finish = np.empty_like(arrivals)
    for i in range(len(arrivals)):
        f = heapq.heappop(free)
        s = arrivals[i] if arrivals[i] > f else f
        e = s + service[i]
        start[i], finish[i] = s, e
        heapq.heappush(free, e)
    return start, finish


def run_priority(arrivals: np.ndarray, service: np.ndarray, key: np.ndarray, c: int) -> tuple[np.ndarray, np.ndarray]:
    """Non-preemptive priority dispatch on c identical servers.

    Whenever a server frees, it takes the waiting parcel with the smallest key.
    key = cutoff gives earliest-deadline-first (EDF); key = arrival index gives
    FIFO and reproduces run() exactly (tested). arrivals must be sorted ascending.
    """
    n = len(arrivals)
    free = [0.0] * c
    heapq.heapify(free)
    wait: list[tuple[float, int]] = []
    start = np.empty(n)
    finish = np.empty(n)
    i = done = 0
    while done < n:
        f = free[0]
        # admit everything that has arrived by the time the next server frees
        while i < n and arrivals[i] <= f:
            heapq.heappush(wait, (key[i], i)); i += 1
        if not wait:  # server idles until the next arrival (admit ties too)
            t = arrivals[i]
            while i < n and arrivals[i] <= t:
                heapq.heappush(wait, (key[i], i)); i += 1
        heapq.heappop(free)
        _, j = heapq.heappop(wait)
        s = arrivals[j] if arrivals[j] > f else f
        start[j], finish[j] = s, s + service[j]
        heapq.heappush(free, finish[j])
        done += 1
    return start, finish


def gamma_service(rng, n: int, mean: float, cv: float) -> np.ndarray:
    """Deterministic-plus-noise service: gamma with given mean and coefficient of variation."""
    if cv <= 0:
        return np.full(n, mean)
    k = 1.0 / cv**2
    return rng.gamma(k, mean / k, n)


def wave_arrivals(rng, departures_s: np.ndarray, counts: np.ndarray, open_h: float, close_h: float):
    """Each route's packages arrive uniformly between (dep - open_h) and (dep - close_h).

    ASSUMPTION (no inbound scans in the dataset): inbound is tied to each
    route's departure. Returns sorted arrivals and the route index per package.
    """
    arr, idx = [], []
    for r, (d, n) in enumerate(zip(departures_s, counts)):
        arr.append(rng.uniform(d - open_h * 3600, d - close_h * 3600, n))
        idx.append(np.full(n, r))
    a, ix = np.concatenate(arr), np.concatenate(idx)
    o = np.argsort(a, kind="stable")
    return a[o], ix[o]


def miss_curve(rng, departures_s, counts, cutoff_h, open_h, close_h, rate_h, cv, c_values, reps=10, policy="fifo"):
    """Mean share of packages finishing after cutoff, and P(any route late), per cell count.

    policy: "fifo" (pooled first-come-first-served) or "edf" (earliest cutoff first).
    miss_ci95 is the half-width of a normal 95% interval over replications.
    """
    mean = 3600.0 / rate_h
    out = []
    for c in c_values:
        miss, route_late, p95_wait = [], [], []
        for _ in range(reps):
            a, ix = wave_arrivals(rng, departures_s, counts, open_h, close_h)
            sv = gamma_service(rng, len(a), mean, cv)
            cut = departures_s[ix] - cutoff_h * 3600
            s, f = run(a, sv, c) if policy == "fifo" else run_priority(a, sv, cut, c)
            late = f > cut
            miss.append(late.mean())
            route_late.append(np.bincount(ix[late], minlength=len(counts)).astype(bool).mean())
            p95_wait.append(np.percentile(s - a, 95) / 60)
        out.append({"cells": int(c), "miss_share": float(np.mean(miss)),
                    "miss_ci95": float(1.96 * np.std(miss, ddof=1) / np.sqrt(reps)) if reps > 1 else None,
                    "routes_late_share": float(np.mean(route_late)), "p95_wait_min": float(np.mean(p95_wait))})
    return out


def cells_needed(rng, departures_s, counts, cutoff_h, open_h, close_h, rate_h, cv, c_start, target=0.01, reps=4, policy="fifo", c_max=400):
    """Smallest c with mean late share < target, scanning down then up from c_start."""
    def ok(c):
        return miss_curve(rng, departures_s, counts, cutoff_h, open_h, close_h, rate_h, cv, [c], reps, policy)[0]["miss_share"] < target
    c = max(1, c_start)
    if ok(c):
        while c > 1 and ok(c - 1):
            c -= 1
        return c
    while c < c_max and not ok(c):
        c += 1
    return c
