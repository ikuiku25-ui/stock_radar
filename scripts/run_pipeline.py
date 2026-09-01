#!/usr/bin/env python3
"""Phase 7: run the full daily pipeline once (spec §5, §12 Phase 7).

Collect (all tickers, via TDnet's fetch_recent — not just the 4
case-study ones) -> price data for newly-seen tickers -> classify new
disclosures -> score new disclosures -> notify S/A ranks -> record
outcomes for scores whose next trading day has arrived.

Meant to be invoked once per trading day by an OS-level scheduler shortly
after market close (see README for cron/launchd/Task Scheduler setup) —
this script does not loop or daemonize itself.

On any stage failure, a summary is logged AND (if --alert-on-error) an
error notification is sent via the same desktop/email channels as S/A
notifications, so failures are noticed without having to check logs.
Exits non-zero if any stage failed, so a scheduler's own failure
monitoring (e.g. cron's MAILTO, or checking exit codes) also catches it.

Usage:
    python scripts/run_pipeline.py --db-path data/stock_radar.db3 --method desktop
    python scripts/run_pipeline.py --db-path data/stock_radar.db3 --method email --alert-on-error
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_radar.db.connection import get_or_init_connection  # noqa: E402
from stock_radar.notification.desktop import send_desktop_notification  # noqa: E402
from stock_radar.notification.email_notifier import send_email_notification  # noqa: E402
from stock_radar.pipeline.logging_config import configure_logging  # noqa: E402
from stock_radar.pipeline.runner import run_daily_pipeline  # noqa: E402

logger = logging.getLogger("stock_radar.pipeline")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-path", default="data/stock_radar.db3")
    parser.add_argument("--log-dir", default="logs")
    parser.add_argument("--method", choices=["desktop", "email", "both", "none"], default="desktop")
    parser.add_argument(
        "--alert-on-error",
        action="store_true",
        help="also send a notification (via --method) if any pipeline stage failed",
    )
    parser.add_argument("--tdnet-limit", type=int, default=300)
    parser.add_argument("--price-period", default="3mo")
    args = parser.parse_args()

    log_path = configure_logging(Path(args.log_dir))
    logger.info("=== Starting daily pipeline run (db=%s) ===", args.db_path)

    notifiers = []
    if args.method in ("desktop", "both"):
        notifiers.append(send_desktop_notification)
    if args.method in ("email", "both"):
        notifiers.append(send_email_notification)

    Path(args.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = get_or_init_connection(args.db_path)
    summary = run_daily_pipeline(conn, notifiers=notifiers, tdnet_limit=args.tdnet_limit, price_period=args.price_period)
    conn.close()

    logger.info(
        "Run summary: new_disclosures=%d tickers_priced=%d classified=%d scored=%d "
        "notifications_sent=%d outcomes_recorded=%d errors=%d",
        summary.new_disclosures, summary.tickers_priced, summary.classified, summary.scored,
        summary.notifications_sent, summary.outcomes_recorded, len(summary.stage_errors),
    )
    for stage, error in summary.stage_errors.items():
        logger.error("Stage %r failed: %s", stage, error)

    print(f"See {log_path} for full logs.")
    print(
        f"new_disclosures={summary.new_disclosures} tickers_priced={summary.tickers_priced} "
        f"classified={summary.classified} scored={summary.scored} "
        f"notifications_sent={summary.notifications_sent} outcomes_recorded={summary.outcomes_recorded}"
    )

    if not summary.ok:
        print(f"FAILED stage(s): {list(summary.stage_errors)}", file=sys.stderr)
        if args.alert_on_error and notifiers:
            error_summary = "; ".join(f"{stage}: {error}" for stage, error in summary.stage_errors.items())
            for notifier in notifiers:
                try:
                    notifier("[Stock Radar] パイプライン実行エラー", f"以下のステージで失敗しました:\n{error_summary}")
                except Exception:  # noqa: BLE001 - don't let a broken alert channel mask the real failure
                    logger.exception("Failed to send error alert notification")
        sys.exit(1)


if __name__ == "__main__":
    main()
