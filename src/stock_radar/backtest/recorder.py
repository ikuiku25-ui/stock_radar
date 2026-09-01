"""Outcome-recording orchestrator (spec §10.1, §10.2).

Deliberately a separate module/execution path from scoring (spec §10.2:
"スコア算出処理と結果記録処理は別モジュール・別実行タイミングとする") —
this is meant to run well after scoring, once the next trading day's price
is actually available, not as part of the same scoring pass.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from stock_radar.collectors.repository import get_available_price_asof

from .outcome import compute_outcome
from .repository import get_next_trading_day_bar, has_outcome, save_outcome


class ScoreNotFoundError(RuntimeError):
    pass


@dataclass
class RecordOutcomeResult:
    outcome_id: Optional[int]
    skipped_reason: Optional[str] = None  # None means it was recorded


def record_outcome_for_score(conn: sqlite3.Connection, score_id: int) -> RecordOutcomeResult:
    if has_outcome(conn, score_id):
        return RecordOutcomeResult(outcome_id=None, skipped_reason="already recorded")

    score = conn.execute(
        "SELECT s.ticker, d.disclosed_at FROM scores s "
        "JOIN disclosures d ON d.disclosure_id = s.disclosure_id "
        "WHERE s.score_id = ?",
        (score_id,),
    ).fetchone()
    if score is None:
        raise ScoreNotFoundError(f"score_id={score_id} not found")

    base_row = get_available_price_asof(conn, score["ticker"], score["disclosed_at"])
    if base_row is None:
        return RecordOutcomeResult(outcome_id=None, skipped_reason="no baseline price data")

    next_row = get_next_trading_day_bar(conn, score["ticker"], base_row["trade_date"])
    if next_row is None:
        return RecordOutcomeResult(outcome_id=None, skipped_reason="next trading day not yet available")

    metrics = compute_outcome(
        prev_close=base_row["close"],
        next_day_open=next_row["open"],
        next_day_high=next_row["high"],
        next_day_low=next_row["low"],
        next_day_close=next_row["close"],
    )
    outcome_id = save_outcome(
        conn, score_id, score["ticker"], metrics, datetime.now(timezone.utc).isoformat()
    )
    return RecordOutcomeResult(outcome_id=outcome_id)
