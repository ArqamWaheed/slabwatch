import numpy as np
import pytest

from slabwatch.forecast import QUANTILES, cdf_at, monotone, p_cross

LV = list(QUANTILES)


def test_median_gives_half():
    vals = np.linspace(150, 250, len(LV))
    assert p_cross(vals[LV.index(0.5)], LV, vals) == pytest.approx(0.5)


def test_interpolates_between_knots():
    lv, v = [0.1, 0.5, 0.9], [100, 200, 300]
    assert cdf_at(150, lv, v) == pytest.approx(0.3)
    assert p_cross(250, lv, v) == pytest.approx(0.3)


def test_tails_extend_linearly_and_clip():
    lv, v = [0.1, 0.5, 0.9], [100, 200, 300]
    assert cdf_at(75, lv, v) == pytest.approx(0.0)       # 0.1 - 0.004*25
    assert cdf_at(90, lv, v) == pytest.approx(0.06)
    assert cdf_at(1000, lv, v) == 1.0
    assert cdf_at(-5, lv, v) == 0.0


def test_cdf_monotone():
    vals = np.sort(np.random.default_rng(1).normal(200, 30, len(LV)))
    xs = np.linspace(50, 350, 200)
    cdf = [cdf_at(x, LV, vals) for x in xs]
    assert all(b >= a - 1e-12 for a, b in zip(cdf, cdf[1:]))
    assert 0 <= min(cdf) and max(cdf) <= 1


def test_point_forecast_is_step():
    v = [180.0] * len(LV)
    assert p_cross(200, LV, v) == 0.0
    assert p_cross(170, LV, v) == 1.0


def test_crossed_quantiles_are_sorted():
    assert monotone([3, 1, 2]).tolist() == [1, 2, 3]
