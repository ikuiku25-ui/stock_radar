#!/usr/bin/env python3
"""Phase 5: notify on newly S/A-ranked scores and mark them watchlisted
(spec §5, §11, §12 Phase 5).

Manual trigger, per spec §12 Phase 5's completion condition ("手動トリガー
で通知確認完了"). Safe to re-run: only un-watchlisted S/A scores are
notified each time (see notification/service.py's module docstring).

Email requires SMTP env vars (STOCK_RADAR_SMTP_HOST/_PORT/_USER/_PASSWORD,
STOCK_RADAR_NOTIFY_EMAIL_TO) — see README. Desktop notification currently
only works on macOS (osascript) and needs no setup.

Usage:
    python scripts/notify_watchlist.py --db-path data/stock_radar.db3 --dry-run
    python scripts/notify_watchlist.py --db-path data/stock_radar.db3 --method desktop
    python scripts/notify_watchlist.py --db-path data/stock_radar.db3 --method email
    python scripts/notify_watchlist.py --db-path data/stock_radar.db3 --method both
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_radar.db.connection import get_connection  # noqa: E402
from stock_radar.notification.desktop import send_desktop_notification  # noqa: E402
from stock_radar.notification.email_notifier import send_email_notification  # noqa: E402
from stock_radar.notification.message import build_notification_message  # noqa: E402
from stock_radar.notification.service import (  # noqa: E402
    find_unwatchlisted_s_a_scores,
    notify_and_watchlist,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-path", default="data/stock_radar.db3")
    parser.add_argument("--method", choices=["desktop", "email", "both"], default="desktop")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print messages without sending or marking watchlisted",
    )
    args = parser.parse_args()

    conn = get_connection(args.db_path)

    if args.dry_run:
        rows = find_unwatchlisted_s_a_scores(conn)
        conn.close()
        if not rows:
            print("(no new S/A-ranked scores to notify)")
            return
        for row in rows:
            message = build_notification_message(
                row["ticker"], row["company_name"], row["title"],
                row["category"], row["notification_rank"], row["total_score"],
            )
            print(f"--- {message.subject} ---")
            print(message.body)
        return

    notifiers = []
    if args.method in ("desktop", "both"):
        notifiers.append(send_desktop_notification)
    if args.method in ("email", "both"):
        notifiers.append(send_email_notification)

    outcomes = notify_and_watchlist(conn, notifiers)
    conn.commit()
    conn.close()

    if not outcomes:
        print("(no new S/A-ranked scores to notify)")
        return
    for outcome in outcomes:
        status = "OK" if outcome.sent else "FAILED"
        suffix = f" ({outcome.error})" if outcome.error else ""
        print(f"[{outcome.ticker}] rank={outcome.notification_rank} -> {status}{suffix}")


if __name__ == "__main__":
    main()
