"""The pot percentage is arithmetic. These cases are the ones that
quietly produce a wrong dashboard if the formula is sloppy."""

from modules.campaigns.pool import obligation, pot_size, summarize


def test_pot_is_expected_views_times_rate():
    assert pot_size(1_000_000, 500) == 500_000


def test_below_the_minimum_owes_nothing():
    assert obligation(999, rate_per_1000_views=2.5, min_views_threshold=1000, cap_amount=None) == 0


def test_views_convert_at_the_campaign_rate():
    assert obligation(2000, rate_per_1000_views=2.5, min_views_threshold=0, cap_amount=None) == 5.0


def test_a_submission_cannot_exceed_its_cap():
    assert obligation(1_000_000, rate_per_1000_views=2.5, min_views_threshold=0, cap_amount=10) == 10


def test_allocated_cannot_exceed_the_pot():
    summary = summarize(100, [80, 40])
    assert summary.allocated == 100
    assert summary.remaining == 0
    assert summary.percent_given == 100
    assert summary.percent_remaining == 0


def test_empty_campaign_has_given_nothing():
    summary = summarize(250.0, [])
    assert summary.allocated == 0
    assert summary.remaining == 250
    assert summary.percent_given == 0
    assert summary.percent_remaining == 100
    assert summary.submissions_counted == 0


def test_percent_given_is_allocated_over_pot():
    # 1,519 views at ₦2.5 / 1K = ₦3.80 of a ₦250 pot → 1.52%
    owed = obligation(1519, rate_per_1000_views=2.5, min_views_threshold=0, cap_amount=None)
    summary = summarize(250, [owed])
    assert owed == 3.80
    assert summary.percent_given == 1.52
    assert summary.percent_remaining == 98.48
