#!/usr/bin/env python3
"""Phase 2 completion-condition script: fetch real TDnet + yfinance data for
the 4 case-study tickers (4840, 7743, 3987, 3907) and persist them with the
full 3-time model, satisfying spec §12 Phase 2's completion condition
("4銘柄分の実データが3時刻モデル込みで保存できる").

Must be run on a machine with real internet access to the unofficial TDnet
API and Yahoo Finance — this sandbox's network policy blocks both (see
README.md "Phase 2" section). Run scripts/tdnet_connectivity_probe.py and
scripts/yfinance_connectivity_probe.py first to sanity-check connectivity
and response shape.

Usage:
    python scripts/collect_case_study_data.py --db-path data/stock_radar.db3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_radar.collectors.repository import (  # noqa: E402
    CASE_STUDY_TICKERS,
    save_disclosure,
    save_price_bars,
)
from stock_radar.collectors.tdnet import TDnetClient, TDnetClientError  # noqa: E402
from stock_radar.collectors.yfinance_client import YFinanceClient  # noqa: E402
from stock_radar.db.connection import get_connection, init_db  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-path", default="data/stock_radar.db3")
    parser.add_argument(
        "--tdnet-limit",
        type=int,
        default=80,
        help="max disclosures for the combined 4-ticker request (API's 'limit' param; default 300 upstream)",
    )
    parser.add_argument("--price-period", default="6mo")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = init_db(str(db_path)) if not db_path.exists() else get_connection(str(db_path))

    # Minimal placeholder rows so the FK on disclosures/price_data is
    # satisfiable. Real company metadata (market cap, sector, etc.) is out
    # of scope for Phase 2 (data collection); it belongs with the scoring
    # module in Phase 4 that actually consumes it for §7's scale comparison.
    for ticker in CASE_STUDY_TICKERS:
        conn.execute(
            "INSERT OR IGNORE INTO companies (ticker, company_name, listing_status, updated_at) "
            "VALUES (?, ?, 'active', datetime('now'))",
            (ticker, ticker),
        )
    conn.commit()

    tdnet = TDnetClient()
    yf_client = YFinanceClient()
    tickers = sorted(CASE_STUDY_TICKERS)

    print(f"[TDnet] fetching disclosures for {', '.join(tickers)} in ONE combined request ...")
    try:
        disclosures = tdnet.fetch_by_tickers(tickers, limit=args.tdnet_limit)
    except TDnetClientError as exc:
        print(f"  FAILED: {exc}", file=sys.stderr)
        disclosures = []

    counts: dict[str, int] = {}
    for disclosure in disclosures:
        save_disclosure(conn, disclosure)
        counts[disclosure.ticker] = counts.get(disclosure.ticker, 0) + 1
    conn.commit()
    for ticker in tickers:
        print(f"  -> {ticker}: saved {counts.get(ticker, 0)} disclosure(s)")

    for ticker in tickers:
        print(f"[yfinance] fetching price history for {ticker} ...")
        bars = yf_client.fetch_daily_bars(ticker, period=args.price_period)
        save_price_bars(conn, bars)
        conn.commit()
        print(f"  -> saved {len(bars)} price bar(s)")

    conn.close()
    print(f"Done. DB at {db_path}")


if __name__ == "__main__":
    main()
