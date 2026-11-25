import math

import numpy as np

from pipeline import speed_segments_web as ssw
from pipeline import tram_stretches as ts


def test_seg_id_is_stable_and_directional():
    a = ssw.seg_id("WRO", "rynek@1_2", "plac@3_4")
    assert a == ssw.seg_id("WRO", "rynek@1_2", "plac@3_4")
    assert a != ssw.seg_id("WRO", "plac@3_4", "rynek@1_2")
    assert a.startswith("WRO-") and len(a) == 4 + ssw.ID_HEX


def test_unique_ids_grow_on_collision(monkeypatch):
    monkeypatch.setattr(ssw, "ID_HEX", 1)
    pairs = [(f"p{i}", f"q{i}") for i in range(40)]      # 40 pairs in 16 one-hex buckets must collide
    ids = ssw.unique_ids("X", pairs)
    assert len(set(ids)) == len(ids)
    assert len(ids[0]) > len("X-") + 1


def test_cap_from_parts_equals_cap_kmh():
    ms = np.array([np.nan, 40.0, 40.0, np.nan, 60.0, np.nan, np.nan])
    for v0 in (30.0, 50.0, 70.0):
        p = {**ts.KIN, "v_cap_kmh": v0}
        msh, msf = ssw.cap_parts(ms)
        assert math.isclose(ssw.cap_from_parts(msh, msf, v0), ts.cap_kmh(ms, p), rel_tol=1e-12)


def test_cap_parts_without_tags():
    assert ssw.cap_parts(None) == (None, 0.0)
    assert ssw.cap_parts(np.array([np.nan, np.nan])) == (None, 0.0)
    assert ssw.cap_from_parts(None, 0.0, 50.0) == 50.0


def test_chain_interval_is_one_minute_per_piece():
    assert ssw.chain_interval_min(1) == 1.0
    assert ssw.chain_interval_min(3) == 3.0


def test_r4_rounds_and_keeps_missing():
    assert ssw.r4(123.456) == 123.5
    assert ssw.r4(None) is None
    assert ssw.r4(float("nan")) is None
    assert ssw.r4(0.0012345) == 0.001234 or ssw.r4(0.0012345) == 0.001235


def test_geom4326_keeps_two_points():
    xy = np.array([[360000.0, 358000.0], [360000.0, 358000.0]])
    g = ssw.geom4326(xy)
    assert len(g) == 2 and all(len(p) == 2 for p in g)
