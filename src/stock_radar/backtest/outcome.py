"""Next-day outcome metrics (spec §10.1). This is the one place in the
project where using "future" data relative to the disclosure is CORRECT
and intentional — outcome_tracking measures what actually happened next,
for backtesting. It must never be read by classification/scoring code
(spec §10.2 — enforced by tests/test_backtest_separation.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .price_limit import upper_limit_price

HIT_PLUS5PCT_THRESHOLD = 5.0
HIT_PLUS10PCT_THRESHOLD = 10.0


@dataclass
class OutcomeMetrics:
    next_day_open: Optional[float]
    next_day_high: Optional[float]
    next_day_low: Optional[float]
    next_day_close: Optional[float]
    prev_close: Optional[float]
    gap_up_pct: Optional[float]
    max_intraday_gain_pct: Optional[float]
    max_intraday_loss_pct: Optional[float]
    hit_plus5pct: bool
    hit_plus10pct: bool
    hit_upper_limit: bool


def compute_outcome(
    prev_close: Optional[float],
    next_day_open: Optional[float],
    next_day_high: Optional[float],
    next_day_low: Optional[float],
    next_day_close: Optional[float],
) -> OutcomeMetrics:
    if not prev_close or prev_close <= 0:
        return OutcomeMetrics(
            next_day_open=next_day_open, next_day_high=next_day_high,
            next_day_low=next_day_low, next_day_close=next_day_close,
            prev_close=prev_close, gap_up_pct=None, max_intraday_gain_pct=None,
            max_intraday_loss_pct=None, hit_plus5pct=False, hit_plus10pct=False,
            hit_upper_limit=False,
        )

    def pct(value: Optional[float]) -> Optional[float]:
        return (value - prev_close) / prev_close * 100 if value is not None else None

    gap_up_pct = pct(next_day_open)
    max_intraday_gain_pct = pct(next_day_high)
    max_intraday_loss_pct = pct(next_day_low)

    hit_plus5pct = max_intraday_gain_pct is not None and max_intraday_gain_pct >= HIT_PLUS5PCT_THRESHOLD
    hit_plus10pct = max_intraday_gain_pct is not None and max_intraday_gain_pct >= HIT_PLUS10PCT_THRESHOLD
    hit_upper_limit = (
        next_day_high is not None and next_day_high >= upper_limit_price(prev_close)
    )

    return OutcomeMetrics(
        next_day_open=next_day_open,
        next_day_high=next_day_high,
        next_day_low=next_day_low,
        next_day_close=next_day_close,
        prev_close=prev_close,
        gap_up_pct=gap_up_pct,
        max_intraday_gain_pct=max_intraday_gain_pct,
        max_intraday_loss_pct=max_intraday_loss_pct,
        hit_plus5pct=hit_plus5pct,
        hit_plus10pct=hit_plus10pct,
        hit_upper_limit=hit_upper_limit,
    )
