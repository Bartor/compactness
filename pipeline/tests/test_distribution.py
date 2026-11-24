import numpy as np

from pipeline import distribution_stats as S


def test_share_at_least_and_at_most():
    v = [10, 20, 30, 40]
    w = [1, 1, 1, 1]
    assert S.share_at_least(v, w, [0, 10, 11, 40, 41]) == [100.0, 100.0, 75.0, 25.0, 0.0]
    assert S.share_at_most(v, w, [5, 10, 30, 40]) == [0.0, 25.0, 75.0, 100.0]


def test_missing_values_are_ignored_and_empty_is_none():
    assert S.share_at_least([np.nan, 5], [1, 1], [5]) == [100.0]
    assert S.share_at_least([np.nan], [1], [0]) is None
    assert S.fgt([1.0], [0.0], 10, 0) is None


def test_weighted_quantile_lower_rule():
    assert S.wquantile([1, 2, 3], [1, 1, 2], 0.5) == 2.0
    assert S.wquantile([1, 2, 3], [1, 1, 2], 0.25) == 1.0
    assert S.wquantile([1, 2, 3], [1, 1, 2], 0.75) == 3.0


def test_fgt():
    v, w, z = [5, 10, 20], [1, 1, 2], 10.0
    assert S.fgt(v, w, z, 0) == 0.25          # only the 5 is strictly below
    assert S.fgt(v, w, z, 1) == 0.125         # gap 0.5, weight 1/4
    assert S.fgt(v, w, z, 2) == 0.0625


def test_palma_equal_and_unequal():
    assert abs(S.palma([5] * 10, [1] * 10) - 0.25) < 1e-12    # equal: 10 % / 40 %
    v = [1] * 9 + [91]
    assert abs(S.palma(v, [1] * 10) - 91 / 4) < 1e-9


def test_ratio_of_means():
    assert S.ratio_of_means([1, 3], [2, 2], [1, 1]) == 100.0
    assert S.ratio_of_means([np.nan, 3], [2, 4], [1, 1]) == 75.0
