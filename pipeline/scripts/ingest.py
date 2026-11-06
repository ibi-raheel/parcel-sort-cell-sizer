"""Step 1: raw JSON -> compact package table (out/packages.npz, out/routes.json)."""
import json, os, sys, time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sizer.ingest import build_table, count_package_ids  # noqa: E402

raw = Path(sys.argv[1])
out = Path(os.environ.get("SIZER_CACHE", Path(__file__).resolve().parents[1] / "out"))
out.mkdir(exist_ok=True)
t = time.time()
T = build_table(raw / "package_data.json", raw / "route_data.json")
n_raw = count_package_ids(raw / "package_data.json")
n = len(T["dims"])
print(f"packages parsed {n:,} | raw PackageID keys {n_raw:,} | {time.time()-t:.0f}s")
assert n == n_raw, "reconciliation failed"
np.savez_compressed(out / "packages.npz", route_i=T["route_i"], zone_i=T["zone_i"], dims=T["dims"])
meta = {
    "route_ids": T["route_ids"],
    "routes": [{k: v for k, v in T["routes"][r].items() if k != "zones"} for r in T["route_ids"]],
    "zone_names": T["zone_names"],
    "reconciliation": {"parsed": n, "raw_key_count": n_raw},
}
(out / "routes.json").write_text(json.dumps(meta))
