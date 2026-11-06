"""Stream-parse the Last Mile Routing Research Challenge training files.

package_data.json contains bare `NaN` tokens (not valid JSON), so the raw
bytes go through a small filter that rewrites them to `null` before ijson
sees them. The file is never loaded whole into memory.
"""
from __future__ import annotations

import json
from pathlib import Path

import ijson
import numpy as np


class NaNToNull:
    """File-like wrapper that replaces the token NaN with null, chunk-safe."""

    def __init__(self, f, chunk: int = 1 << 20):
        self.f, self.chunk, self.carry = f, chunk, b""

    def read(self, n: int = -1) -> bytes:
        if n == 0:  # ijson probes with read(0) to detect bytes vs str
            return b""
        data = self.carry + self.f.read(self.chunk if n is None or n < 0 else max(n, 8))
        if not data:
            return b""
        out = data.replace(b"NaN", b"null")
        # hold back a trailing partial token ("N" or "Na") until the next read
        k = 2 if out.endswith(b"Na") else 1 if out.endswith(b"N") else 0
        out, self.carry = (out[:-k], out[-k:]) if k and len(out) > k else (out, b"")
        return out


def load_routes(path: Path) -> dict:
    with open(path, "rb") as f:
        raw = json.load(f)
    routes = {}
    for rid, r in raw.items():
        routes[rid] = {
            "station": r["station_code"],
            "date": r["date_YYYY_MM_DD"],
            "departure_utc": r["departure_time_utc"],
            "capacity_cm3": r["executor_capacity_cm3"],
            "zones": {sid: s.get("zone_id") for sid, s in r["stops"].items()},
        }
    return routes


def iter_packages(path: Path):
    """Yield (route_id, stop_id, depth, width, height) for every package."""
    with open(path, "rb") as f:
        for rid, stops in ijson.kvitems(NaNToNull(f), "", use_float=True):
            for sid, pkgs in stops.items():
                for p in pkgs.values():
                    d = p["dimensions"]
                    yield rid, sid, d["depth_cm"], d["width_cm"], d["height_cm"]


def count_package_ids(path: Path, chunk: int = 1 << 24) -> int:
    """Independent reconciliation count: raw occurrences of the key prefix."""
    n, tail, key = 0, b"", b'"PackageID_'
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            buf = tail + b
            n += buf.count(key)
            tail = buf[-(len(key) - 1):]  # shorter than the key: no double count
    return n


def build_table(pkg_path: Path, route_path: Path) -> dict:
    routes = load_routes(route_path)
    rids = sorted(routes)
    rindex = {r: i for i, r in enumerate(rids)}
    zone_names: dict[str, int] = {}
    route_i, zone_i, dims = [], [], []
    for rid, sid, dd, ww, hh in iter_packages(pkg_path):
        z = routes[rid]["zones"].get(sid)
        z = z if isinstance(z, str) else "NA"  # a few stops carry NaN zone_id
        route_i.append(rindex[rid])
        zone_i.append(zone_names.setdefault(z, len(zone_names)))
        dims.append((dd, ww, hh))
    dims = np.sort(np.asarray(dims, dtype=np.float32), axis=1)[:, ::-1]  # L >= M >= S
    return {
        "route_ids": rids,
        "routes": routes,
        "route_i": np.asarray(route_i, dtype=np.int32),
        "zone_i": np.asarray(zone_i, dtype=np.int32),
        "zone_names": list(zone_names),
        "dims": np.ascontiguousarray(dims),
    }
