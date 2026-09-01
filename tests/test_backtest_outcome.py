from __future__ import annotations

import pytest

from stock_radar.backtest.outcome import compute_outcome


def test_computes_percentages_relative_to_prev_close():
    metrics = compute_outcome(
        prev_close=1000.0, next_day_open=1020.0, next_day_high=1060.0,
        next_day_low=990.0, next_day_close=1030.0,
    )
    assert metrics.gap_up_pct == pytest.approx(2.0)
    assert metrics.max_intraday_gain_pct == pytest.approx(6.0)
    assert metrics.max_intraday_loss_pct == pytest.approx(-1.0)


def test_hit_plus5pct_true_at_exactly_5_percent():
    metrics = compute_outcome(
        prev_close=1000.0, next_day_open=1000.0, next_day_high=1050.0,
        next_day_low=1000.0, next_day_close=1000.0,
    )
    assert metrics.hit_plus5pct is True
    assert metrics.hit_plus10pct is False


def test_hit_plus10pct_true_at_10_percent():
    metrics = compute_outcome(
        prev_close=1000.0, next_day_open=1000.0, next_day_high=1100.0,
        next_day_low=1000.0, next_day_close=1000.0,
    )
    assert metrics.hit_plus10pct is True


def test_hit_upper_limit_true_when_high_reaches_limit_price():
    # prev_close=1250 -> limit width 300 -> upper limit price 1550
    metrics = compute_outcome(
        prev_close=1250.0, next_day_open=1250.0, next_day_high=1550.0,
        next_day_low=1250.0, next_day_close=1550.0,
    )
    assert metrics.hit_upper_limit is True


def test_hit_upper_limit_false_when_high_below_limit():
    metrics = compute_outcome(
        prev_close=1250.0, next_day_open=1250.0, next_day_high=1500.0,
        next_day_low=1250.0, next_day_close=1500.0,
    )
    assert metrics.hit_upper_limit is False


def test_none_prev_close_returns_none_percentages_without_crashing():
    metrics = compute_outcome(
        prev_close=None, next_day_open=100.0, next_day_high=110.0,
        next_day_low=95.0, next_day_close=105.0,
    )
    assert metrics.gap_up_pct is None
    assert metrics.hit_plus5pct is False
    assert metrics.hit_upper_limit is False


def test_zero_prev_close_does_not_divide_by_zero():
    metrics = compute_outcome(
        prev_close=0.0, next_day_open=100.0, next_day_high=110.0,
        next_day_low=95.0, next_day_close=105.0,
    )
    assert metrics.gap_up_pct is None


def test_missing_next_day_high_leaves_gain_metrics_none():
    metrics = compute_outcome(
        prev_close=1000.0, next_day_open=1000.0, next_day_high=None,
        next_day_low=None, next_day_close=None,
    )
    assert metrics.max_intraday_gain_pct is None
    assert metrics.hit_plus5pct is False
    assert metrics.hit_upper_limit is False
