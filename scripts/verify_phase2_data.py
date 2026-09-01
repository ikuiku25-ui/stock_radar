#!/usr/bin/env python3
"""Sanity-check script for Phase 2's completion condition: inspect a
collected DB to confirm the 3-time model, dataset_tag, and avg_volume_20d
are populated as expected.

Usage:
    python3 scripts/verify_phase2_data.py --db-path data/stock_radar.db3
"""

from __future__ import annotations

import argparse
import sqlite3


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default="data/stock_radar.db3")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db_path)
    conn.row_factory = sqlite3.Row

    print("=== companies ===")
    for row in conn.execute("SELECT ticker, listing_status FROM companies ORDER BY ticker"):
        print(dict(row))

    print("\n=== disclosures (per ticker/dataset_tag) ===")
    for row in conn.execute(
        "SELECT ticker, dataset_tag, COUNT(*) AS n FROM disclosures GROUP BY ticker, dataset_tag ORDER BY ticker"
    ):
        print(dict(row))

    print("\n--- sample disclosure row (3-time model) ---")
    row = conn.execute(
        "SELECT ticker, title, disclosed_at, market_available_at, system_available_at, "
        "fetched_at, availability_confidence FROM disclosures ORDER BY disclosure_id LIMIT 1"
    ).fetchone()
    print(dict(row) if row else "(no disclosures found)")

    print("\n=== price_data (rows per ticker, avg_volume_20d coverage) ===")
    for row in conn.execute(
        "SELECT ticker, COUNT(*) AS n, "
        "SUM(CASE WHEN avg_volume_20d IS NOT NULL THEN 1 ELSE 0 END) AS n_with_avg "
        "FROM price_data GROUP BY ticker ORDER BY ticker"
    ):
        print(dict(row))

    conn.close()


if __name__ == "__main__":
    main()
