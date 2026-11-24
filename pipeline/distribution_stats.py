"""Population-weighted distribution statistics used by pipeline.distribution (pure functions, no I/O).

All functions take a value array ``v`` and a weight array ``w`` (residents of the cell) and ignore entries where the
value is not finite or the weight is not positive.  They return None when nothing is left (missing, never 0).
"""
from __future__ import annotations

import numpy as np


def _clean(v, w) -> tuple[np.ndarray, np.ndarray]:
    v = np.asarray(v, dtype=np.float64)
    w = np.asarray(w, dtype=np.float64)
    m = np.isfinite(v) & np.isfinite(w) & (w > 0)
    return v[m], w[m]


def share_at_least(v, w, xs) -> list[float] | None:
    """Inverted cumulative curve: 100 x share of the weight with value >= x, for each x in xs."""
    v, w = _clean(v, w)
    tot = w.sum()
    if tot <= 0:
        return None
    o = np.argsort(v, kind="stable")
    vs, cw = v[o], np.concatenate([[0.0], np.cumsum(w[o])])
    # weight with value >= x = total - weight with value < x
    idx = np.searchsorted(vs, np.asarray(xs, dtype=np.float64), side="left")
    return [min(100.0, max(0.0, float(100.0 * (tot - cw[i]) / tot))) for i in idx]


def share_at_most(v, w, xs) -> list[float] | None:
    """100 x share of the weight with value <= x (used for headways: service at least every x minutes)."""
    v, w = _clean(v, w)
    tot = w.sum()
    if tot <= 0:
        return None
    o = np.argsort(v, kind="stable")
    vs, cw = v[o], np.concatenate([[0.0], np.cumsum(w[o])])
    idx = np.searchsorted(vs, np.asarray(xs, dtype=np.float64), side="right")
    return [min(100.0, max(0.0, float(100.0 * cw[i] / tot))) for i in idx]


def wquantile(v, w, q: float) -> float | None:
    """Weighted quantile, 'lower' rule: the smallest value whose cumulative weight share reaches q."""
    v, w = _clean(v, w)
    if w.sum() <= 0:
        return None
    o = np.argsort(v, kind="stable")
    vs, c = v[o], np.cumsum(w[o]) / w.sum()
    i = int(np.searchsorted(c, q - 1e-12, side="left"))
    return float(vs[min(i, len(vs) - 1)])


def wmean(v, w) -> float | None:
    v, w = _clean(v, w)
    return None if w.sum() <= 0 else float((v * w).sum() / w.sum())


def fgt(v, w, z: float, alpha: int) -> float | None:
    """Foster-Greer-Thorbecke index: weighted mean of ((z - y) / z)^alpha over y < z (0 otherwise); 0..1."""
    v, w = _clean(v, w)
    if w.sum() <= 0 or not z > 0:
        return None
    gap = np.where(v < z, (z - v) / z, 0.0)
    term = np.where(v < z, gap ** alpha, 0.0)
    return float((term * w).sum() / w.sum())


def lorenz_at(v, w, p: float) -> float | None:
    """Lorenz ordinate: share of the weighted total of v held by the poorest p of the weight (linear in between)."""
    v, w = _clean(v, w)
    tot = (v * w).sum()
    if w.sum() <= 0 or tot <= 0:
        return None
    o = np.argsort(v, kind="stable")
    cp = np.concatenate([[0.0], np.cumsum(w[o]) / w.sum()])
    cl = np.concatenate([[0.0], np.cumsum(v[o] * w[o]) / tot])
    return float(np.interp(p, cp, cl))


def palma(v, w) -> float | None:
    """Palma ratio: share held by the top 10 % of residents / share held by the bottom 40 %."""
    lo, hi = lorenz_at(v, w, 0.4), lorenz_at(v, w, 0.9)
    if lo is None or hi is None or lo <= 0:
        return None
    return float((1.0 - hi) / lo)


def ratio_of_means(acc, prox, w) -> float | None:
    """100 x sum(w * acc) / sum(w * prox) over cells with finite acc and positive weight."""
    acc = np.asarray(acc, dtype=np.float64)
    prox = np.asarray(prox, dtype=np.float64)
    w = np.asarray(w, dtype=np.float64)
    m = np.isfinite(acc) & np.isfinite(prox) & (w > 0)
    den = (prox[m] * w[m]).sum()
    return None if den <= 0 else float(100.0 * (acc[m] * w[m]).sum() / den)
