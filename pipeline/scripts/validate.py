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
# time holdout: size from days before the split, test on days after (baseline = mean rule)
import numpy as np  # noqa: E402
hold = []
for s_ in S["stations"]:
    d = json.loads((ROOT.parent / f'public/data/station-{s_["station"]}.json').read_text())["daily"]
    tr = np.array([x["packages"] for x in d if x["date"] < "2018-08-15"]); te = np.array([x["packages"] for x in d if x["date"] >= "2018-08-15"])
    hold.append({"station": s_["station"], "train_days": len(tr), "test_days": len(te),
                 "test_days_over_train_mean": float((te > tr.mean()).mean()),
                 "test_days_over_train_p90": float((te > np.percentile(tr, 90)).mean())})
doc = {"holdout": hold, "hand_calc": hand, "mmc": checks, "sizing_compare": under, "reconciliation": S["dataset"]["reconciliation"]}
(ROOT.parent / "public/data/validation.json").write_text(json.dumps(doc, indent=1))
print(json.dumps(doc, indent=1))
