"""Offline tests for YFinanceClient: the yfinance Ticker is faked with a
pandas DataFrame shaped like its real .history() output."""

from __future__ import annotations

import pandas as pd
import pytest

from stock_radar.collectors.yfinance_client import YFinanceClient


class FakeTicker:
    def __init__(self, symbol, history_df):
        self.symbol = symbol
        self._history_df = history_df

    def history(self, period=None, interval=None):
        return self._history_df


def _sample_history():
    dates = pd.date_range("2026-08-17", periods=5, freq="D")
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "High": [105.0, 106.0, 107.0, 108.0, 109.0],
            "Low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "Close": [103.0, 104.0, 105.0, 106.0, 107.0],
            "Volume": [1000, 2000, 3000, 4000, 5000],
        },
        index=dates,
    )


def _make_client(history_df):
    captured = {}

    def factory(symbol):
        captured["symbol"] = symbol
        return FakeTicker(symbol, history_df)

    client = YFinanceClient(ticker_factory=factory)
    return client, captured


def test_appends_tokyo_suffix_to_symbol():
    client, captured = _make_client(_sample_history())
    client.fetch_daily_bars("7203")
    assert captured["symbol"] == "7203.T"


def test_bar_count_matches_history_rows():
    client, _ = _make_client(_sample_history())
    bars = client.fetch_daily_bars("7203")
    assert len(bars) == 5


def test_ohlc_values_and_session_type():
    client, _ = _make_client(_sample_history())
    bars = client.fetch_daily_bars("7203")
    first = bars[0]
    assert first.trade_date == "2026-08-17"
    assert first.open == 100.0
    assert first.high == 105.0
    assert first.low == 99.0
    assert first.close == 103.0
    assert first.volume == 1000
    assert first.session_type == "close"
    assert first.market_snapshot_at == "2026-08-17T15:00:00+09:00"


def test_first_bar_has_no_avg_volume_20d():
    """No prior trading days exist yet, so the trailing average is undefined
    rather than silently using a partial/zero window."""
    client, _ = _make_client(_sample_history())
    bars = client.fetch_daily_bars("7203")
    assert bars[0].avg_volume_20d is None


def test_avg_volume_20d_excludes_current_day():
    """Look-ahead guard: bar[i]'s avg_volume_20d must be computed only from
    volumes strictly before day i (spec §6.2/§8.2)."""
    client, _ = _make_client(_sample_history())
    bars = client.fetch_daily_bars("7203")
    # bar index 2 (2026-08-19): trailing volumes are [1000, 2000] -> avg 1500
    assert bars[2].avg_volume_20d == pytest.approx(1500.0)
    # bar index 4 (2026-08-21): trailing volumes are [1000,2000,3000,4000] -> avg 2500
    assert bars[4].avg_volume_20d == pytest.approx(2500.0)
    # None of the averages should include that same day's own volume.
    for i, bar in enumerate(bars):
        if bar.avg_volume_20d is not None:
            assert bar.avg_volume_20d != bar.volume


def test_avg_volume_20d_window_caps_at_20_days():
    dates = pd.date_range("2026-01-01", periods=25, freq="D")
    volumes = list(range(1, 26))  # 1..25, distinct so window boundaries are checkable
    history = pd.DataFrame(
        {
            "Open": volumes, "High": volumes, "Low": volumes, "Close": volumes,
            "Volume": volumes,
        },
        index=dates,
    )
    client, _ = _make_client(history)
    bars = client.fetch_daily_bars("7203")
    # bar index 24 (25th day): trailing window should be days 5..24 (volumes 5..24), i.e. last 20 prior days
    expected = sum(range(5, 25)) / 20
    assert bars[24].avg_volume_20d == pytest.approx(expected)
