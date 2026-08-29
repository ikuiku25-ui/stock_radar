#!/usr/bin/env python3
"""Phase 4 manual review helper (spec §12: "スコアが期待レンジ内に収まるか
確認"). Prints each scored disclosure's title next to its score breakdown.

Usage:
    python scripts/review_scores.py --db-path data/stock_radar.db3
    python scripts/review_scores.py --db-path data/stock_radar.db3 --ticker 4840
    python scripts/review_scores.py --db-path data/stock_radar.db3 --min-rank A
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_radar.db.connection import get_connection  # noqa: E402

RANK_ORDER = {"S": 3, "A": 2, "B": 1, "none": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-path", default="data/stock_radar.db3")
    parser.add_argument("--ticker", default=None)
    parser.add_argument("--min-rank", choices=["S", "A", "B", "none"], default="none")
    args = parser.parse_args()

    conn = get_connection(args.db_path)
    query = (
        "SELECT s.ticker, d.disclosed_at, d.title, s.material_score, "
        "s.supply_demand_score, s.theme_score, s.total_score, s.notification_rank "
        "FROM scores s JOIN disclosures d ON d.disclosure_id = s.disclosure_id"
    )
    params: list = []
    if args.ticker:
        query += " WHERE s.ticker = ?"
        params.append(args.ticker)
    query += " ORDER BY s.ticker, d.disclosed_at"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    min_rank_value = RANK_ORDER[args.min_rank]
    shown = 0
    for row in rows:
        if RANK_ORDER[row["notification_rank"]] < min_rank_value:
            continue
        shown += 1
        print(f"[{row['ticker']}] {row['disclosed_at']}  rank={row['notification_rank']}")
        print(f"  {row['title']}")
        print(
            f"  material={row['material_score']}  supply_demand={row['supply_demand_score']}  "
            f"theme={row['theme_score']}  total={row['total_score']}"
        )
        print()

    print(f"({shown}/{len(rows)} scored disclosure(s) shown)")


if __name__ == "__main__":
    main()
