import io, json
import numpy as np
from sizer.ingest import NaNToNull, iter_packages, count_package_ids
from sizer.envelope import within, share


def _wrap_read_all(raw: bytes, chunk: int) -> bytes:
    w = NaNToNull(io.BufferedReader(io.BytesIO(raw)), chunk=chunk)
    out = b""
    while True:
        b = w.read(chunk)
        if not b:
            return out
        out += b


def test_nan_filter_survives_every_split_point():
    raw = b'{"a": NaN, "b": [NaN,1.5,NaN], "Name": "NaNa"}'
    for chunk in range(1, 12):
        out = _wrap_read_all(raw, chunk)
        assert json.loads(out)["b"] == [None, 1.5, None]


def test_iter_and_count_on_fixture(tmp_path):
    doc = {"R1": {"AA": {"PackageID_1": {"time_window": {"start_time_utc": "NaN"}, "dimensions": {"depth_cm": 10, "width_cm": 20, "height_cm": 5}},
                         "PackageID_2": {"dimensions": {"depth_cm": 1, "width_cm": 2, "height_cm": 3}}}},
           "R2": {"BB": {"PackageID_3": {"dimensions": {"depth_cm": 4, "width_cm": 5, "height_cm": 6}}}}}
    p = tmp_path / "p.json"
    p.write_bytes(json.dumps(doc).replace('"NaN"', "NaN").encode())
    rows = list(iter_packages(p))
    assert len(rows) == 3 == count_package_ids(p, chunk=7)
    assert rows[0] == ("R1", "AA", 10, 20, 5)


def test_envelope_box_rule():
    d = np.array([[60, 45, 35], [61, 10, 5], [50, 46, 5], [50, 40, 36], [30, 20, 0.5]], float)
    assert within(d, 60, 45, 35).tolist() == [True, False, False, False, True]
    assert within(d, 60, 45, 35, min_s=1).tolist() == [True, False, False, False, False]
    assert share(d, max_l=60, max_m=45, max_s=35) == 0.4
