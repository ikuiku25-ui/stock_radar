"""Daily OHLCV collector via yfinance (spec §4.1, §6.2, §8.2).

RISK NOTICE (spec 補足): yfinance is an unofficial Yahoo Finance wrapper;
Yahoo's terms of service around automated/bulk fetching are unconfirmed
("要確認"). Used here for personal, non-commercial analysis only, at a
daily-bar polling cadence — not intraday/high-frequency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import yfinance as yf

DEFAULT_TICKER_SUFFIX = ".T"  # Tokyo Stock Exchange
# spec §6.2/§8.2: volume_ratio's denominator is always the trailing 20
# trading days EXCLUDING the day being evaluated.
VOLUME_AVG_WINDOW = 20


@dataclass
class PriceBar:
    ticker: str
    trade_date: str  # 'YYYY-MM-DD'
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[int]
    avg_volume_20d: Optional[float]
    market_snapshot_at: str
    session_type: str = "close"


class YFinanceClient:
    def __init__(
        self,
        ticker_suffix: str = DEFAULT_TICKER_SUFFIX,
        ticker_factory: Callable = yf.Ticker,
    ) -> None:
        self._ticker_suffix = ticker_suffix
        self._ticker_factory = ticker_factory

    def fetch_daily_bars(self, ticker: str, period: str = "3mo") -> list[PriceBar]:
        """Fetch daily bars for `ticker` and compute avg_volume_20d for each
        bar from the days strictly before it (never the bar's own volume).
        """
        symbol = f"{ticker}{self._ticker_suffix}"
        history = self._ticker_factory(symbol).history(period=period, interval="1d")
        return _history_to_bars(ticker, history)


def _history_to_bars(ticker: str, history) -> list[PriceBar]:
    bars: list[PriceBar] = []
    trailing_volumes: list[float] = []

    for trade_date_ts, row in history.iterrows():
        # Compute the average BEFORE appending today's volume, so today is
        # never included in its own trailing average (look-ahead guard).
        window = trailing_volumes[-VOLUME_AVG_WINDOW:]
        avg_volume_20d = sum(window) / len(window) if window else None

        volume = row.get("Volume")
        trailing_volumes.append(volume if volume is not None else 0.0)

        trade_date = trade_date_ts.strftime("%Y-%m-%d")
        bars.append(
            PriceBar(
                ticker=ticker,
                trade_date=trade_date,
                open=_safe_float(row.get("Open")),
                high=_safe_float(row.get("High")),
                low=_safe_float(row.get("Low")),
                close=_safe_float(row.get("Close")),
                volume=int(volume) if volume is not None else None,
                avg_volume_20d=avg_volume_20d,
                market_snapshot_at=f"{trade_date}T15:00:00+09:00",
                session_type="close",
            )
        )
    return bars


def _safe_float(value) -> Optional[float]:
    return float(value) if value is not None else None
