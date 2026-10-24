import pytest

from slabwatch.bill_estimate import cliff_cost, estimate


def test_protected_one_previous_slab():
    e = estimate(180, "protected", 2.0)
    assert e.energy == pytest.approx(100 * 10.54 + 80 * 13.01)
    assert e.fixed == 600
    assert e.total == pytest.approx(3617, abs=1)  # worked example in docs/TARIFF.md


def test_unprotected_whole_month_at_slab_rate():
    e = estimate(210, "unprotected", 2.0)
    assert e.energy == pytest.approx(210 * 33.10)
    assert e.total == pytest.approx(10232, abs=1)


def test_protected_cannot_exceed_200():
    with pytest.raises(ValueError):
        estimate(201, "protected")


def test_cliff_cost_counts_six_months():
    c = cliff_cost(195, 205, 180)
    assert c["penalty_months"] == 6 and c["next_months_extra"] > 0 and c["total_extra"] > c["this_month_extra"]
