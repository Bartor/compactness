import numpy as np
import pytest

from pipeline.density_service import (class_code, density_class, map_class, weighted_midranks,
                                      weighted_spearman)


def test_midranks_with_ties():
    r = weighted_midranks(np.array([1.0, 1.0, 3.0]), np.array([1.0, 1.0, 2.0]))
    assert r.tolist() == [1.0, 1.0, 3.0]          # tie group weight 2 below 0 -> 1; next group below 2, half of 2 -> 3


def test_spearman_perfect_and_reversed():
    w = np.ones(4)
    assert weighted_spearman([1, 2, 3, 4], [10, 20, 30, 40], w) == pytest.approx(1.0)
    assert weighted_spearman([1, 2, 3, 4], [4, 3, 2, 1], w) == pytest.approx(-1.0)


def test_spearman_with_ties_hand_checked():
    # x ranks 0.5 1.5 2.5 3.5, y ranks 1 1 3 3: cov 4, var 5 and 4 -> 4 / sqrt(20)
    assert weighted_spearman([1, 2, 3, 4], [1, 1, 2, 2], np.ones(4)) == pytest.approx(4 / np.sqrt(20))


def test_spearman_weighted_hand_checked():
    # weights 1 1 2, x = 1 2 3, y = 1 3 2: x ranks .5 1.5 3, y ranks .5 3.5 2 -> cov 1.5, var 4.5 and 4.5 -> 1/3
    assert weighted_spearman([1, 2, 3], [1, 3, 2], [1, 1, 2]) == pytest.approx(1 / 3)


def test_spearman_constant_is_none():
    assert weighted_spearman([1, 2, 3], [5, 5, 5], np.ones(3)) is None


def test_classes():
    d = density_class(np.array([0.0, 2499.9, 2500.0, 9999.0, 10000.0, 30000.0]))
    assert d.tolist() == [1, 1, 2, 2, 3, 3]
    assert class_code(np.array([1, 2, 3]), np.array([1, 2, 3])).tolist() == [0, 4, 8]
    # map classes: dense cells by service (0 poor, 1 medium, 2 good); sparse cells 3 (served) or 4 (not)
    d = np.array([1, 1, 1, 2, 2, 2, 3, 3, 3])
    s = np.array([1, 2, 3, 1, 2, 3, 1, 2, 3])
    assert map_class(d, s).tolist() == [4, 3, 3, 0, 1, 2, 0, 1, 2]
