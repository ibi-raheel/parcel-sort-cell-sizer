"""P90 demand forecasting for cell sizing: gradient-boosted quantile model vs simple baselines.

Sizing hinges on the P90 day and on how much of it lands in each departure wave.
This module forecasts the 90th percentile of parcel volume at three grains:

  day    one unit per (station, date)
  wave   one unit per (station, date, local departure hour)
  route  one unit per route

Forecast for date D is made at origin O = D - h (h = horizon in days). Known at the
origin: the planned route count and departure schedule for D (stations plan routes
ahead with their delivery partners), the vehicle mix, weekday, and the station's
history up to and including O. Nothing dated after O enters a feature.

The model forecasts the P90 of packages per route and multiplies by the planned route
count. Because the route count is known, q90(y) = routes x q90(y / routes) exactly, and
training with sample_weight = routes makes the training loss the pinball loss on y.

Validation is rolling-origin with whole dates as blocks: each fold tests a block of
consecutive dates and trains only on units dated <= (first test date - h).
"""
from __future__ import annotations

import datetime as _dt

import numpy as np

Q = 0.9
FEATURES = ["station", "dow", "hour", "routes", "cap_mean", "big_share", "routes_ratio",
            "ppr7", "ppr_all", "ppr_last", "ppr_dow", "ppr_sd", "ppr_hour", "glob_dow"]
# Wave-size buckets for the size-aware simple rule: 1 | 2-3 | 4-6 | 7+ routes (fixed in advance, not tuned).
SIZE_EDGES = [1.5, 3.5, 6.5]


# ---------------------------------------------------------------- metrics
def pinball(y, f, q: float = Q) -> np.ndarray:
    """Per-unit pinball (quantile) loss. Mean over units is the usual score."""
    d = np.asarray(y, float) - np.asarray(f, float)
    return np.maximum(q * d, (q - 1) * d)


def scores(y, f, q: float = Q) -> dict:
    y = np.asarray(y, float); f = np.asarray(f, float)
    return {"pinball": float(pinball(y, f, q).mean()), "coverage": float((y <= f).mean()),
            "forecast_over_actual": float(f.sum() / y.sum()),
            "mean_shortfall_when_under": float(np.mean((y - f)[y > f])) if (y > f).any() else 0.0}


def block_bootstrap_diff(loss_a, loss_b, blocks, n_boot: int = 2000, seed: int = 0) -> dict:
    """Paired bootstrap over whole blocks (dates) of mean(loss_a - loss_b) and of 1 - sum(a)/sum(b)."""
    rng = np.random.default_rng(seed)
    loss_a = np.asarray(loss_a, float); loss_b = np.asarray(loss_b, float)
    ub, inv = np.unique(blocks, return_inverse=True)
    A = np.bincount(inv, loss_a, len(ub)); B = np.bincount(inv, loss_b, len(ub)); N = np.bincount(inv, minlength=len(ub))
    idx = rng.integers(0, len(ub), size=(n_boot, len(ub)))
    sa, sb, sn = A[idx].sum(1), B[idx].sum(1), N[idx].sum(1)
    diff = (sa - sb) / sn
    ok = sb > 0                      # relative change is undefined when the baseline loss is zero
    rel = 1 - sa[ok] / sb[ok]
    return {"mean_diff": float((A.sum() - B.sum()) / N.sum()), "mean_diff_ci90": np.percentile(diff, [5, 95]).tolist(),
            "rel_improvement": float(1 - A.sum() / B.sum()) if B.sum() > 0 else None,
            "rel_improvement_ci90": np.percentile(rel, [5, 95]).tolist() if ok.mean() > 0.95 else None,
            "p_a_better": float((diff < 0).mean()), "n_blocks": int(len(ub)), "n_units": int(N.sum())}


# ---------------------------------------------------------------- panel
class Panel:
    """Dense station x day (x hour) tallies of packages and routes, for history features."""

    def __init__(self, station, day, hour, cap, n, dates: list[str]):
        self.st_names = sorted(set(station))
        sidx = {s: i for i, s in enumerate(self.st_names)}
        self.s = np.array([sidx[x] for x in station]); self.d = np.asarray(day); self.h = np.asarray(hour)
        self.cap = np.asarray(cap, float); self.n = np.asarray(n, float)
        self.dates = dates
        self.dow = np.array([_dt.date.fromisoformat(x).weekday() for x in dates])
        S, D = len(self.st_names), len(dates)
        self.Y = np.zeros((S, D)); self.R = np.zeros((S, D))
        np.add.at(self.Y, (self.s, self.d), self.n); np.add.at(self.R, (self.s, self.d), 1)
        self.YH = np.zeros((S, 24, D)); self.RH = np.zeros((S, 24, D))
        np.add.at(self.YH, (self.s, self.h, self.d), self.n); np.add.at(self.RH, (self.s, self.h, self.d), 1)
        self.big = self.cap > np.median(self.cap)

    def units(self, level: str) -> dict:
        """Aggregate routes into forecast units. Returns arrays keyed by column name."""
        if level == "route":
            key = np.arange(len(self.n))
        elif level == "wave":
            key = (self.s * 100 + self.h) * 1000 + self.d
        elif level == "day":
            key = self.s * 1000 + self.d
        else:
            raise ValueError(level)
        uk, inv = np.unique(key, return_inverse=True)
        m = len(uk)
        first = np.full(m, -1); first[inv[::-1]] = np.arange(len(inv))[::-1]
        routes = np.bincount(inv, minlength=m).astype(float)
        return {"s": self.s[first], "d": self.d[first], "h": self.h[first] if level != "day" else np.full(m, -1),
                "routes": routes, "y": np.bincount(inv, self.n, m), "cap_mean": np.bincount(inv, self.cap, m) / routes,
                "big_share": np.bincount(inv, self.big.astype(float), m) / routes, "route_unit": inv}

    # history known at origin o (inclusive) for station s
    def _ppr(self, s, lo, hi, hour=None):
        lo = max(lo, 0)
        if hi < lo:
            return np.nan
        if hour is None:
            y, r = self.Y[s, lo:hi + 1].sum(), self.R[s, lo:hi + 1].sum()
        else:
            y, r = self.YH[s, hour, lo:hi + 1].sum(), self.RH[s, hour, lo:hi + 1].sum()
        return y / r if r > 0 else np.nan

    def features(self, U: dict, h: int) -> np.ndarray:
        rows = []
        gY, gR = self.Y.sum(0), self.R.sum(0)
        for s, d, hr, routes, cm, bs in zip(U["s"], U["d"], U["h"], U["routes"], U["cap_mean"], U["big_share"]):
            o = d - h
            obs = np.flatnonzero(self.R[s, :max(o + 1, 0)] > 0)
            daily_ppr = self.Y[s, obs] / self.R[s, obs] if len(obs) else np.array([])
            same = [k for k in obs if self.dow[k] == self.dow[d]]
            g_obs = np.arange(max(o + 1, 0))
            g_all = gY[g_obs].sum() / gR[g_obs].sum() if gR[g_obs].sum() else np.nan
            g_dow = [k for k in g_obs if self.dow[k] == self.dow[d]]
            g_dw = gY[g_dow].sum() / gR[g_dow].sum() if g_dow and gR[g_dow].sum() else np.nan
            routes_day = self.R[s, d]
            rows.append([
                s, self.dow[d], hr if hr >= 0 else np.nan, routes, cm, bs,
                routes_day / self.R[s, obs].mean() if len(obs) else np.nan,
                self._ppr(s, o - 6, o), self._ppr(s, 0, o),
                daily_ppr[-1] if len(daily_ppr) else np.nan,
                self.Y[s, same[-1]] / self.R[s, same[-1]] if same else np.nan,
                daily_ppr.std(ddof=1) if len(daily_ppr) > 2 else np.nan,
                self._ppr(s, 0, o, hr) if hr >= 0 else np.nan,
                g_dw / g_all if g_all == g_all and g_dw == g_dw else np.nan,
            ])
        return np.asarray(rows, float)

    def history_days(self, U: dict, h: int) -> np.ndarray:
        return np.array([(self.R[s, :max(d - h + 1, 0)] > 0).sum() for s, d in zip(U["s"], U["d"])])


# ---------------------------------------------------------------- baselines (y-level)
def _unit_history(P: Panel, s, hr, level):
    if level == "day":
        return P.Y[s], P.R[s] > 0
    if level == "wave":
        return P.YH[s, hr], P.R[s] > 0        # a station-day with no route in this hour counts as 0
    return P.Y[s] / np.maximum(P.R[s], 1), P.R[s] > 0   # route level: mean packages per route that day


def baseline_trailing_mean(P: Panel, U: dict, h: int, level: str, mult: float = 1.3, window: int = 7) -> np.ndarray:
    """Mean of the unit's volume over observed days in (O-window, O], times mult (all history if none)."""
    out = np.empty(len(U["y"]))
    for i, (s, d, hr) in enumerate(zip(U["s"], U["d"], U["h"])):
        y, ok = _unit_history(P, s, hr, level)
        o = d - h
        k = [j for j in range(max(o - window + 1, 0), o + 1) if ok[j]] or [j for j in range(0, o + 1) if ok[j]]
        out[i] = mult * y[k].mean() if k else np.nan
    return out


def baseline_last_week(P: Panel, U: dict, h: int, level: str) -> tuple[np.ndarray, np.ndarray]:
    """Same weekday last week (D-7, else D-14, if <= origin); else the unscaled trailing mean. Returns (forecast, used_fallback)."""
    tm = baseline_trailing_mean(P, U, h, level, mult=1.0)
    out = tm.copy(); fb = np.ones(len(out), bool)
    for i, (s, d, hr) in enumerate(zip(U["s"], U["d"], U["h"])):
        y, ok = _unit_history(P, s, hr, level)
        for lag in (7, 14):
            j = d - lag
            if j >= 0 and j <= d - h and ok[j]:
                out[i] = y[j]; fb[i] = False
                break
    return out, fb


def route_ppr_raw(X: np.ndarray, by_hour: bool = False) -> np.ndarray:
    """routes x trailing-7-day packages per route (all history if the window is empty).

    by_hour: use the station's packages per route for that departure hour (all history
    up to the origin) instead, falling back to the station figure when the hour is new.
    """
    c = {f: i for i, f in enumerate(FEATURES)}
    ppr = np.where(np.isnan(X[:, c["ppr7"]]), X[:, c["ppr_all"]], X[:, c["ppr7"]])
    if by_hour:
        ppr = np.where(np.isnan(X[:, c["ppr_hour"]]), ppr, X[:, c["ppr_hour"]])
    return X[:, c["routes"]] * ppr


# ---------------------------------------------------------------- model
def make_model(seed: int = 0, q: float = Q):
    from sklearn.ensemble import HistGradientBoostingRegressor
    return HistGradientBoostingRegressor(loss="quantile", quantile=q, max_iter=300, learning_rate=0.04,
                                         max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1.0,
                                         categorical_features=[0], random_state=seed)


def rolling_folds(test_days: np.ndarray, start: int, block: int):
    """Consecutive-date test blocks from `start` to the last day."""
    last = int(test_days.max())
    return [(t0, min(t0 + block - 1, last)) for t0 in range(start, last + 1, block)]


def run_level(P: Panel, level: str, h: int, start: int = 14, block: int = 5, min_hist: int = 3, seed: int = 0,
              eval_mask_fn=None) -> dict:
    """Rolling-origin evaluation of the quantile model and the baselines at one grain and horizon."""
    U = P.units(level)
    X = P.features(U, h)
    y, routes = U["y"], U["routes"]
    ppr = y / routes
    hist = P.history_days(U, h)
    raw = route_ppr_raw(X)
    raw_h = route_ppr_raw(X, by_hour=True)
    names = ["model", "trailing_mean_x1.3", "same_weekday_last_week", "routes_x_ppr_calibrated"]
    if level != "day":
        names.append("routes_x_hour_ppr_calibrated")
    if level == "wave":
        names.append("routes_x_ppr_calibrated_by_wave_size")
    size_b = np.digitize(routes, SIZE_EDGES)
    f = {k: np.full(len(y), np.nan) for k in names}
    f["trailing_mean_x1.3"] = baseline_trailing_mean(P, U, h, level)
    f["same_weekday_last_week"], lw_fb = baseline_last_week(P, U, h, level)
    folds = []
    for t0, t1 in rolling_folds(U["d"], start, block):
        tr = (U["d"] <= t0 - h) & ~np.isnan(raw)
        te = (U["d"] >= t0) & (U["d"] <= t1) & (hist >= min_hist)
        if tr.sum() < 30 or te.sum() == 0:
            continue
        cols = np.flatnonzero(~np.isnan(X[tr]).all(0))   # e.g. hour is undefined at the day grain
        mdl = make_model(seed).fit(X[tr][:, cols], ppr[tr], sample_weight=routes[tr])
        f["model"][te] = routes[te] * mdl.predict(X[te][:, cols])
        k = float(np.quantile(y[tr] / raw[tr], Q))       # calibrated on the training fold only
        f["routes_x_ppr_calibrated"][te] = k * raw[te]
        kh = float(np.quantile(y[tr] / raw_h[tr], Q))
        if level != "day":
            f["routes_x_hour_ppr_calibrated"][te] = kh * raw_h[te]
        k_size = {}
        if level == "wave":
            # same rule, but one multiplier per wave-size bucket, each fitted on the training fold only
            for b in np.unique(size_b[te]):
                trb = tr & (size_b == b)
                k_size[int(b)] = float(np.quantile(y[trb] / raw[trb], Q)) if trb.sum() >= 20 else k
                teb = te & (size_b == b)
                f["routes_x_ppr_calibrated_by_wave_size"][teb] = k_size[int(b)] * raw[teb]
        folds.append({"test_days": [P.dates[t0], P.dates[t1]], "train_units": int(tr.sum()), "test_units": int(te.sum()),
                      "calibration_k": k, "calibration_k_hour": kh, "calibration_k_by_wave_size": k_size})
    ev = ~np.isnan(f["model"])
    if eval_mask_fn is not None:
        ev &= eval_mask_fn(U)
    for k in f:
        ev &= ~np.isnan(f[k])
    res = {"level": level, "horizon_days": h, "units": int(ev.sum()), "folds": folds,
           "scores": {k: scores(y[ev], v[ev]) for k, v in f.items()},
           "last_week_fallback_share": float(lw_fb[ev].mean())}
    loss_m = pinball(y[ev], f["model"][ev])
    res["model_vs"] = {k: block_bootstrap_diff(loss_m, pinball(y[ev], f[k][ev]), U["d"][ev], seed=seed)
                       for k in f if k != "model"}
    res["_eval"] = {"mask": ev, "U": U, "f": f}
    return res
