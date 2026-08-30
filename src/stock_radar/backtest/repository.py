"""Persistence for outcome_tracking (spec §10.1, §10.2).

outcome_tracking.score_id is UNIQUE (Phase 0 addition, enforcing spec
§10.2's "1対0または1対1" relationship) — has_outcome() lets callers check
before inserting instead of catching sqlite3.IntegrityError, since a
missing outcome (not yet enough time has passed) is an expected, common
case, not an error.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from .outcome import OutcomeMetrics


def has_outcome(conn: sqlite3.Connection, score_id: int) -> bool:
    return conn.execute("SELECT 1 FROM outcome_tracking WHERE score_id = ?", (score_id,)).fetchone() is not None


def get_next_trading_day_bar(
    conn: sqlite3.Connection, ticker: str, after_trade_date: str
) -> Optional[sqlite3.Row]:
    """First confirmed 'close' bar strictly after after_trade_date."""
    return conn.execute(
        "SELECT * FROM price_data WHERE ticker = ? AND session_type = 'close' "
        "AND trade_date > ? ORDER BY trade_date ASC LIMIT 1",
        (ticker, after_trade_date),
    ).fetchone()


def save_outcome(
    conn: sqlite3.Connection, score_id: int, ticker: str, metrics: OutcomeMetrics, recorded_at: str
) -> int:
    cur = conn.execute(
        """
        INSERT INTO outcome_tracking
            (score_id, ticker, next_day_open, next_day_high, next_day_low,
             next_day_close, prev_close, gap_up_pct, max_intraday_gain_pct,
             max_intraday_loss_pct, hit_plus5pct, hit_plus10pct,
             hit_upper_limit, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            score_id,
            ticker,
            metrics.next_day_open,
            metrics.next_day_high,
            metrics.next_day_low,
            metrics.next_day_close,
            metrics.prev_close,
            metrics.gap_up_pct,
            metrics.max_intraday_gain_pct,
            metrics.max_intraday_loss_pct,
            1 if metrics.hit_plus5pct else 0,
            1 if metrics.hit_plus10pct else 0,
            1 if metrics.hit_upper_limit else 0,
            recorded_at,
        ),
    )
    return cur.lastrowid
