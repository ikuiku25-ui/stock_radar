"""Persistence for collector output, plus the look-ahead-bias read guard
for price_data (spec §8.2). Scoring/backtest code (later phases) MUST read
prices through get_available_price_asof() rather than querying price_data
directly, so the intraday-disclosure exclusion rule cannot be bypassed by
accident.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, time as dt_time, timedelta, timezone

from .tdnet import RawDisclosure
from .yfinance_client import PriceBar

JST = timezone(timedelta(hours=9))
INTRADAY_CUTOFF = dt_time(15, 0)  # spec §8.2: "15:00より前"

# spec §10.3 / §12 Phase 3: fixed case-study set, never used for statistical
# validation.
CASE_STUDY_TICKERS = frozenset({"4840", "7743", "3987", "3907"})


def dataset_tag_for_ticker(ticker: str) -> str:
    return "case_study" if ticker in CASE_STUDY_TICKERS else "statistical"


def save_disclosure(conn: sqlite3.Connection, disclosure: RawDisclosure) -> int:
    """Insert one collected disclosure.

    category / positive_material_raw / negative_penalty_raw / is_hard_block
    are left at their schema defaults — material classification is Phase 3.

    raw_text is a placeholder (the title) at collection time: full-text PDF
    extraction belongs with the Phase 3 classifier that will consume it,
    not the collector, so it is deliberately deferred rather than
    duplicated here.
    """
    market_available_at = disclosure.disclosed_at  # spec §8.1: ≒ disclosed_at
    cur = conn.execute(
        """
        INSERT INTO disclosures
            (ticker, title, raw_text, pdf_url, disclosed_at, market_available_at,
             system_available_at, fetched_at, availability_confidence, dataset_tag)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            disclosure.ticker,
            disclosure.title,
            disclosure.title,
            disclosure.pdf_url,
            disclosure.disclosed_at,
            market_available_at,
            disclosure.system_available_at,
            disclosure.fetched_at,
            disclosure.availability_confidence,
            dataset_tag_for_ticker(disclosure.ticker),
        ),
    )
    return cur.lastrowid


def save_price_bars(conn: sqlite3.Connection, bars: list[PriceBar]) -> None:
    """Upsert price bars (re-running a fetch for the same ticker/date/session
    just refreshes the row rather than erroring or duplicating)."""
    conn.executemany(
        """
        INSERT OR REPLACE INTO price_data
            (ticker, trade_date, open, high, low, close, volume,
             avg_volume_20d, market_snapshot_at, session_type)
        VALUES (:ticker, :trade_date, :open, :high, :low, :close, :volume,
                :avg_volume_20d, :market_snapshot_at, :session_type)
        """,
        [bar.__dict__ for bar in bars],
    )


def is_intraday_disclosure(disclosed_at_iso: str) -> bool:
    """True if disclosed_at falls before 15:00 JST (spec §8.2): the trading
    day's price_data is then still unconfirmed and must not be used."""
    return to_jst(disclosed_at_iso).time() < INTRADAY_CUTOFF


def get_available_price_asof(
    conn: sqlite3.Connection, ticker: str, disclosed_at_iso: str
) -> sqlite3.Row | None:
    """Return the most recent CONFIRMED 'close' price_data row visible to a
    disclosure made at disclosed_at_iso, enforcing spec §8.2:
      - Intraday (pre-15:00) disclosure: only trading days strictly BEFORE
        the disclosure date are visible (that day's own data is unconfirmed).
      - Post-close (>=15:00) disclosure: that day's confirmed close is
        visible (and used) if present, else the most recent prior day.
    Always restricted to session_type='close' — 'pts_reference' rows are
    never returned here, by construction.
    """
    dt = to_jst(disclosed_at_iso)
    disclosure_date = dt.date().isoformat()

    if dt.time() < INTRADAY_CUTOFF:
        query = (
            "SELECT * FROM price_data WHERE ticker = ? AND session_type = 'close' "
            "AND trade_date < ? ORDER BY trade_date DESC LIMIT 1"
        )
    else:
        query = (
            "SELECT * FROM price_data WHERE ticker = ? AND session_type = 'close' "
            "AND trade_date <= ? ORDER BY trade_date DESC LIMIT 1"
        )
    return conn.execute(query, (ticker, disclosure_date)).fetchone()


def to_jst(iso_str: str) -> datetime:
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(JST)
