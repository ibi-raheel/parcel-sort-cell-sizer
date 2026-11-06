"""Robot pick-envelope fit on sorted package dimensions (L >= M >= S, cm)."""
import numpy as np


def within(dims: np.ndarray, max_l: float, max_m: float, max_s: float, min_s: float = 0.0) -> np.ndarray:
    """Boolean mask: package fits a box envelope max_l x max_m x max_s and is at least min_s thick."""
    L, M, S = dims[:, 0], dims[:, 1], dims[:, 2]
    return (L <= max_l) & (M <= max_m) & (S <= max_s) & (S >= min_s)


def share(dims, **env) -> float:
    return float(within(dims, **env).mean()) if len(dims) else float("nan")


def sweep_longest(dims, l_values, max_m, max_s, min_s=0.0):
    """Sortable share as the longest-side limit moves (other limits held)."""
    return [share(dims, max_l=l, max_m=max_m, max_s=max_s, min_s=min_s) for l in l_values]
