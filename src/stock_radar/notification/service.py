"""Notification orchestration (spec §5, §12 Phase 5): only S/A-ranked
scores are notified (spec §5's pipeline: "通知（S/Aランクのみ）").

`watchlist` doubles as the "already notified" record — a score is only
inserted there once at least one notifier succeeds, so re-running this
naturally skips scores already handled AND retries scores whose delivery
previously failed entirely (nothing to mark them "already tried and
failed" would help with, since the fix is usually on the human's end —
e.g. SMTP credentials).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from .message import build_notification_message

NotifierFn = Callable[[str, str], None]  # (subject, body) -> None; raises on failure


@dataclass
class NotificationOutcome:
    score_id: int
    ticker: str
    notification_rank: str
    sent: bool
    error: Optional[str] = None


def find_unwatchlisted_s_a_scores(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT s.score_id, s.ticker, s.notification_rank, s.total_score,
               d.title, d.category, c.company_name
        FROM scores s
        JOIN disclosures d ON d.disclosure_id = s.disclosure_id
        JOIN companies c ON c.ticker = s.ticker
        LEFT JOIN watchlist w ON w.score_id = s.score_id
        WHERE s.notification_rank IN ('S', 'A') AND w.watchlist_id IS NULL
        ORDER BY s.scored_at
        """
    ).fetchall()


def notify_and_watchlist(
    conn: sqlite3.Connection, notifiers: list[NotifierFn]
) -> list[NotificationOutcome]:
    outcomes = []
    for row in find_unwatchlisted_s_a_scores(conn):
        message = build_notification_message(
            row["ticker"],
            row["company_name"],
            row["title"],
            row["category"],
            row["notification_rank"],
            row["total_score"],
        )

        errors = []
        any_sent = False
        for notifier in notifiers:
            try:
                notifier(message.subject, message.body)
                any_sent = True
            except Exception as exc:  # noqa: BLE001 - report per-notifier, don't abort the batch
                errors.append(str(exc))

        if any_sent:
            conn.execute(
                "INSERT INTO watchlist (ticker, score_id, added_at, note) VALUES (?, ?, ?, ?)",
                (row["ticker"], row["score_id"], datetime.now(timezone.utc).isoformat(), message.subject),
            )

        outcomes.append(
            NotificationOutcome(
                score_id=row["score_id"],
                ticker=row["ticker"],
                notification_rank=row["notification_rank"],
                sent=any_sent,
                error="; ".join(errors) if errors else None,
            )
        )
    return outcomes
