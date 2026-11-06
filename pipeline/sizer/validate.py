"""Validation helpers: DES against M/M/c theory, and Little's law."""
import numpy as np

from .queueing import erlang_c, wq_mean
from .sim import run


def mmc_check(lam_h: float, mu_h: float, c: int, n: int = 200_000, seed: int = 7) -> dict:
    rng = np.random.default_rng(seed)
    a = np.cumsum(rng.exponential(3600 / lam_h, n))
    sv = rng.exponential(3600 / mu_h, n)
    s, f = run(a, sv, c)
    w = (s - a)[n // 10:]  # drop warm-up
    wq_sim = w.mean() / 3600
    pw_sim = (w > 1e-9).mean()
    # Little's law on the queue: time-average number waiting vs lambda_hat * mean wait
    a2, s2 = a[n // 10:], s[n // 10:]
    t0, t1 = a2.min(), a2.max()
    # Little's law, measured independently: sample the queue length at random instants
    ts = rng.uniform(t0, t1, 50_000)
    Lq = float((np.searchsorted(a2, ts, "right") - np.searchsorted(np.sort(s2), ts, "right")).mean())
    lam_hat = len(a2) / (t1 - t0)
    return {"lam_h": lam_h, "mu_h": mu_h, "c": c,
            "wq_theory_min": wq_mean(lam_h, mu_h, c) * 60, "wq_sim_min": wq_sim * 60,
            "pwait_theory": erlang_c(lam_h, mu_h, c), "pwait_sim": float(pw_sim),
            "littles_Lq": float(Lq), "littles_lambdaW": float(lam_hat * w.mean())}
