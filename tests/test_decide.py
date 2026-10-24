import pytest

from slabwatch.decide import decide, escalated


def test_act_example_from_spec():
    d = decide(p10=190, p50=215, p90=240, p_cross=0.8, units_so_far=141, days_elapsed=19, cycle_days=30)
    assert d.verdict == "act"
    assert d.days_left == 11
    assert d.daily_budget == pytest.approx(59 / 11)
    assert "5.4 units/day for 11 days" in d.message and "running at 7.4" in d.message
    assert d.message_ur


def test_already_over_beats_everything():
    d = decide(p10=230, p50=260, p90=300, p_cross=1.0, units_so_far=205, days_elapsed=20)
    assert d.verdict == "already_over"


def test_safe_when_far_below():
    d = decide(p10=110, p50=125, p90=140, p_cross=0.0, units_so_far=40, days_elapsed=10)
    assert d.verdict == "safe"
    assert "Nothing to do" in d.message


def test_watch_band():
    d = decide(p10=170, p50=185, p90=205, p_cross=0.2, units_so_far=110, days_elapsed=18)
    assert d.verdict == "watch"


def test_unsure_when_spread_wide_and_straddles():
    d = decide(p10=120, p50=180, p90=260, p_cross=0.35, units_so_far=25, days_elapsed=4)
    assert d.verdict == "unsure"


def test_wide_spread_but_clearly_below_is_safe():
    d = decide(p10=60, p50=100, p90=150, p_cross=0.0, units_so_far=15, days_elapsed=4)
    assert d.verdict == "safe"


def test_never_alarmist_and_states_assumptions():
    for pc, so in ((0.9, 150), (0.0, 20), (1.0, 250)):
        d = decide(p10=150, p50=200, p90=250, p_cross=pc, units_so_far=so, days_elapsed=15)
        assert "!" not in d.message
        assert any("200 units" in a for a in d.assumptions)
        assert any("may have changed" in a for a in d.assumptions)


def test_threshold_and_penalty_are_settings():
    d = decide(p10=250, p50=280, p90=310, p_cross=0.4, units_so_far=150, days_elapsed=15,
               threshold=301, penalty_months=1)
    assert d.threshold == 301 and "1 months" in d.assumptions[0]


def test_day_zero_rejected():
    with pytest.raises(ValueError):
        decide(1, 1, 1, 0, 0, 0)


def test_escalation_alerts_once():
    assert escalated(None, "act")
    assert not escalated("act", "act")
    assert escalated("act", "already_over")
    assert not escalated(None, "watch")       # watch never pushes
    assert not escalated("already_over", "act")
