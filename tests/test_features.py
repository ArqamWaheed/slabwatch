import datetime as dt
import math

import numpy as np
import pandas as pd
import pytest

from slabwatch.features import CUT_DAYS, FEATURES, build_rows, cut_features, interp_cum

START = dt.date(2018, 6, 1)


def _daily(kwh):
    return pd.DataFrame({"house": 1, "date": pd.to_datetime([START + dt.timedelta(days=i) for i in range(len(kwh))]),
                         "kwh": kwh, "coverage": 1.0})


def _temps(n):
    return {str(START + dt.timedelta(days=i)): 30 + 5 * math.sin(i / 9) for i in range(n)}


META = pd.DataFrame([{"house": 1, "n_acs": 2, "area_sqft": 1000, "people": 5}])


def test_no_future_units_in_features():
    """Changing usage AFTER the cut day must not change any feature at that cut."""
    rng = np.random.default_rng(0)
    base = rng.uniform(5, 15, 60)
    a = build_rows(_daily(base), META, _temps(60), step=30)
    for cut in CUT_DAYS:
        changed = base.copy()
        # second window starts on day 30: perturb its days >= cut (and the first window's days >= cut too)
        changed[30 + cut:] *= 3
        b = build_rows(_daily(changed), META, _temps(60), step=30)
        ra = a[(a.cut == cut) & (a.cycle_start == START + dt.timedelta(days=30))][list(FEATURES)]
        rb = b[(b.cut == cut) & (b.cycle_start == START + dt.timedelta(days=30))][list(FEATURES)]
        pd.testing.assert_frame_equal(ra.reset_index(drop=True), rb.reset_index(drop=True))
        # ...but the target does change, so the test is not vacuous
        ta = a[(a.cut == cut) & (a.cycle_start == START + dt.timedelta(days=30))]["final_units"].iloc[0]
        tb = b[(b.cut == cut) & (b.cycle_start == START + dt.timedelta(days=30))]["final_units"].iloc[0]
        assert tb > ta


def test_cut_features_ignores_points_after_cut():
    pts = [(i, 10.0 * i) for i in range(1, 11)]
    f1 = cut_features(pts[:5], 5, START, [30] * 5, [30] * 25)
    f2 = cut_features(pts + [(30, 9999.0)], 5, START, [30] * 5, [30] * 25)
    assert pd.Series(f1).equals(pd.Series(f2))  # NaN-aware


def test_target_is_scale_free():
    rng = np.random.default_rng(2)
    kwh = rng.uniform(3, 9, 45)
    a = build_rows(_daily(kwh), META, _temps(45), step=15)
    b = build_rows(_daily(kwh * 7.5), META, _temps(45), step=15)
    assert np.allclose(a["ratio"], b["ratio"])
    for col in ("recent_over_rate", "prev_total_over_naive", "last_cycle_ratio", "days_elapsed"):
        assert np.allclose(a[col], b[col], equal_nan=True)
    assert np.allclose(b["rate_so_far"], 7.5 * a["rate_so_far"])


def test_constant_usage_gives_ratio_one():
    df = build_rows(_daily(np.full(30, 6.0)), META, _temps(30))
    assert len(df) == len(CUT_DAYS)
    assert np.allclose(df["ratio"], 1.0)
    assert np.allclose(df["final_units"], 180.0)


def test_live_readings_interpolate_like_training():
    # readings only on day 5 and day 12: rate_last_3 uses the interpolated curve
    f = cut_features([(5, 50.0), (12, 120.0)], 12, START, [30] * 12, [30] * 18)
    assert f["units_so_far"] == 120.0 and f["rate_last_3_days"] == pytest.approx(10.0)
    assert interp_cum([(0, 0), (10, 100)], 2.5) == 25


def test_zero_days_dropped():
    kwh = np.full(30, 6.0)
    kwh[10] = 0.0
    assert build_rows(_daily(kwh), META, _temps(30)).empty
