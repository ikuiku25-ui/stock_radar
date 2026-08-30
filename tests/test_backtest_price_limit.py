from __future__ import annotations

import pytest

from stock_radar.backtest.price_limit import limit_width, upper_limit_price


@pytest.mark.parametrize(
    "prev_close,expected_width",
    [
        (88.0, 30),      # ticker 3907's real price range
        (150.0, 50),
        (640.0, 100),    # ticker 3987's real price range
        (1250.0, 300),   # ticker 4840's real price range
        (4870.0, 700),   # ticker 7743's real price range
    ],
)
def test_limit_width_bands(prev_close, expected_width):
    assert limit_width(prev_close) == expected_width


def test_upper_limit_price_adds_width_to_prev_close():
    assert upper_limit_price(1250.0) == pytest.approx(1250.0 + 300)


def test_very_high_price_uses_fallback_width():
    assert limit_width(60_000_000) == 10_000_000
