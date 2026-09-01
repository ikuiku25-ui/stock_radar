#!/usr/bin/env python3
"""Phase 3 manual review helper (spec §12: "適合率・再現率を手動確認").

Prints every disclosure's title next to its assigned classification, so a
human can spot-check whether the fresh keyword dictionary
(src/stock_radar/classification/keywords.py) is getting real disclosures
right before moving on to Phase 4 scoring.

Usage:
    python scripts/review_classifications.py --db-path data/stock_radar.db3
    python scripts/review_classifications.py --db-path data/stock_radar.db3 --ticker 4840
    python scripts/review_classifications.py --db-path data/stock_radar.db3 --unclassified-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_radar.db.connection import get_connection  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-path", default="data/stock_radar.db3")
    parser.add_argument("--ticker", default=None, help="restrict to one ticker")
    parser.add_argument(
        "--unclassified-only",
        action="store_true",
        help="show only disclosures with no positive category and no HARD_BLOCK/SOFT_NEGATIVE match",
    )
    args = parser.parse_args()

    conn = get_connection(args.db_path)
    query = (
        "SELECT ticker, disclosed_at, title, category, positive_material_raw, "
        "negative_penalty_raw, is_hard_block FROM disclosures"
    )
    conditions = []
    params: list = []
    if args.ticker:
        conditions.append("ticker = ?")
        params.append(args.ticker)
    if args.unclassified_only:
        conditions.append("category IS NULL AND negative_penalty_raw = 0 AND is_hard_block = 0")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY ticker, disclosed_at"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        print("(no matching disclosures)")
        return

    for row in rows:
        flags = []
        if row["is_hard_block"]:
            flags.append("HARD_BLOCK")
        if row["negative_penalty_raw"] < 0:
            flags.append(f"SOFT_NEGATIVE({row['negative_penalty_raw']})")
        flags_str = f" [{', '.join(flags)}]" if flags else ""

        print(f"[{row['ticker']}] {row['disclosed_at']}")
        print(f"  {row['title']}")
        print(f"  category={row['category'] or '(none)'}  positive_raw={row['positive_material_raw']}{flags_str}")
        print()

    print(f"({len(rows)} disclosure(s) shown)")


if __name__ == "__main__":
    main()
