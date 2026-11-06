"""Validation run -> public/data/validation.json"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sizer.validate import mmc_check  # noqa: E402
from sizer.queueing import cells_hand  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
S = json.loads((ROOT.parent / "public/data/summary.json").read_text())
st = json.loads((ROOT.parent / "public/data/station-DLA7.json").read_text())
dd = st["design_day"]
exc = 1 - st["envelope"]["sortable_share"]
hand = {"station": "DLA7", "design_packages": dd["design_packages"], "sort_span_h": dd["sort_span_h"],
        "exception_rate": exc, "rate_h": 500,
        "by_hand": f'ceil({dd["design_packages"]} x (1 - {exc:.4f}) / ({dd["sort_span_h"]:.3f} x 500))',
        "by_hand_value": -(-dd["design_packages"] * (1 - exc) // (dd["sort_span_h"] * 500)),
        "tool_value": st["sizing"]["cells_hand_p90"]}
hand["by_hand_value"] = int(hand["by_hand_value"])
checks = [mmc_check(1400, 500, 4), mmc_check(1800, 500, 4), mmc_check(4000, 500, 9)]
# sizing on mean vs P90+wave, all stations
under = [{"station": s["station"], "mean_rule": s["cells_hand_mean"], "p90_rule": s["cells_hand_p90"],
          "erlang": s["cells_erlang"], "des": s["cells_des"]} for s in S["stations"]]
# time holdout, split into route coverage vs packages per route. The sample's daily totals
# track how many routes were sampled, so the "trend" is tested on each factor separately.
import numpy as np  # noqa: E402
hold = []
for s_ in S["stations"]:
    st_ = json.loads((ROOT.parent / f'public/data/station-{s_["station"]}.json').read_text())
    d, rr = st_["daily"], st_["daily_routes"]
    pk = np.array([x["packages"] for x in d], float); rr = np.array(rr, float)
    tr = np.array([x["date"] < "2018-08-15" for x in d]); te = ~tr
    ppr = pk / rr
    hold.append({"station": s_["station"], "train_days": int(tr.sum()), "test_days": int(te.sum()),
                 "test_days_over_train_mean": float((pk[te] > pk[tr].mean()).mean()),
                 "test_days_over_train_p90": float((pk[te] > np.percentile(pk[tr], 90)).mean()),
                 "routes_train_mean": float(rr[tr].mean()), "routes_test_mean": float(rr[te].mean()),
                 "ppr_train_mean": float(ppr[tr].mean()), "ppr_test_mean": float(ppr[te].mean()),
                 "ppr_change": float(ppr[te].mean() / ppr[tr].mean() - 1),
                 "routes_change": float(rr[te].mean() / rr[tr].mean() - 1)})
coverage = [{"station": s_["station"], **s_["coverage"]} for s_ in S["stations"]]
# Erlang C at a 30-minute threshold collapses to the stability condition c > a + ln(100)/(mu*t)
mu, t = 500.0, 0.5
erl_collapse = {"mu_h": mu, "t_h": t, "margin_erlangs": float(np.log(100) / (mu * t)),
                "note": "P(Wq>t) = C e^{-(c mu - lam) t} < 0.01 holds once c - a > ln(100)/(mu t) = 0.018, so c_erlang = ceil(a) = hand rule unless a is within 0.018 of an integer"}
# week-1 ranking: how far each assumption can move (relative to its base) before the count rises
rank = {}
for s_ in S["stations"]:
    for t_ in s_["tornado"]:
        f_ = t_["flip_up_at"]
        if f_ is None:
            continue
        rel = abs(f_ - t_["base"]) / (1 + t_["base"]) if t_["param"] == "uplift" else abs(f_ - t_["base"]) / t_["base"]
        rank.setdefault(t_["param"], []).append(rel)
week1 = sorted(({"param": k, "median_rel_margin": float(np.median(v)), "stations_with_flip": len(v)} for k, v in rank.items()),
               key=lambda r: r["median_rel_margin"])
ladder = [{"station": s_["station"], "bound": s_["cells_bound"], "bound_1pct": s_["cells_bound_1pct"], "edf": s_["cells_edf20"], "fifo": s_["cells_fifo20"],
           "fifo_8rep": s_["cells_des"], "cells_90pct": s_["cells_90pct_confidence"]} for s_ in S["stations"]]
doc = {"holdout": hold, "coverage": coverage, "erlang_collapse": erl_collapse, "week1_ranking": week1, "ladder": ladder, "hand_calc": hand, "mmc": checks, "sizing_compare": under, "reconciliation": S["dataset"]["reconciliation"]}
(ROOT.parent / "public/data/validation.json").write_text(json.dumps(doc, indent=1))
print(json.dumps(doc, indent=1))
