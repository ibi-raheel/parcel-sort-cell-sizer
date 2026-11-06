"""Steady-state M/M/c (Erlang C) sizing and the back-of-envelope hand calculation."""
import math


def erlang_c(lam: float, mu: float, c: int) -> float:
    """Probability an arrival waits, P(W>0), for M/M/c. Returns 1.0 if unstable."""
    a = lam / mu
    if c <= a:
        return 1.0
    # numerically stable recursion for the Erlang B, then convert to C
    b = 1.0
    for k in range(1, c + 1):
        b = a * b / (k + a * b)
    rho = a / c
    return b / (1 - rho + rho * b)


def wq_mean(lam: float, mu: float, c: int) -> float:
    """Mean queue wait for M/M/c (same time unit as 1/mu)."""
    pw = erlang_c(lam, mu, c)
    return math.inf if pw >= 1.0 and c <= lam / mu else pw / (c * mu - lam)


def p_wait_exceeds(lam: float, mu: float, c: int, t: float) -> float:
    """P(Wq > t) for M/M/c."""
    if c <= lam / mu:
        return 1.0
    return erlang_c(lam, mu, c) * math.exp(-(c * mu - lam) * t)


def cells_erlang(lam: float, mu: float, t: float, target: float = 0.01, c_max: int = 200) -> int:
    """Smallest c with P(Wq > t) < target."""
    for c in range(1, c_max + 1):
        if p_wait_exceeds(lam, mu, c, t) < target:
            return c
    return c_max


def cells_hand(volume: float, window_h: float, rate_per_cell_h: float, exception_rate: float) -> int:
    """cells = ceil(V (1 - e) / (W * r)). The spreadsheet rule."""
    return math.ceil(volume * (1 - exception_rate) / (window_h * rate_per_cell_h))
