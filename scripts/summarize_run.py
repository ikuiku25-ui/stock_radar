#!/usr/bin/env python3
"""Print a Markdown summary of the current DB state, meant to be appended
to GitHub Actions' $GITHUB_STEP_SUMMARY so the result is viewable directly
on the workflow run's page (e.g. from a phone's browser) — no artifact
download or SQLite viewer needed.

Usage:
    python scripts/summarize_run.py --db-path data/stock_radar.db3
    python scripts/summarize_run.py --db-path data/stock_radar.db3 >> "$GITHUB_STEP_SUMMARY"
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
    parser.add_argument("--min-rank", choices=["S", "A", "B", "none"], default="B")
    parser.add_argument("--top-n", type=int, default=20)
    args = parser.parse_args()

    conn = get_connection(args.db_path)

    has_schema = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'disclosures'"
    ).fetchone()
    if not has_schema:
        print("## Stock Radar 実行サマリー\n")
        print("（データベースが未初期化のため、サマリーを生成できませんでした。ログを確認してください）\n")
        conn.close()
        return

    disclosure_count = conn.execute("SELECT COUNT(*) AS n FROM disclosures").fetchone()["n"]
    score_count = conn.execute("SELECT COUNT(*) AS n FROM scores").fetchone()["n"]
    statistical_count = conn.execute(
        "SELECT COUNT(*) AS n FROM disclosures WHERE dataset_tag = 'statistical'"
    ).fetchone()["n"]

    print("## Stock Radar 実行サマリー\n")
    print(f"- 開示件数: {disclosure_count}（うち統計検証用: {statistical_count}）")
    print(f"- スコア件数: {score_count}\n")

    print("### ランク別件数\n")
    print("| Rank | 件数 |")
    print("|---|---|")
    for row in conn.execute(
        "SELECT notification_rank, COUNT(*) AS n FROM scores GROUP BY notification_rank ORDER BY notification_rank"
    ):
        print(f"| {row['notification_rank']} | {row['n']} |")
    print()

    min_rank_value = RANK_ORDER[args.min_rank]
    rows = conn.execute(
        """
        SELECT s.ticker, c.company_name, d.title, s.notification_rank,
               s.material_score, s.supply_demand_score, s.theme_score, s.total_score
        FROM scores s
        JOIN disclosures d ON d.disclosure_id = s.disclosure_id
        JOIN companies c ON c.ticker = s.ticker
        ORDER BY s.total_score DESC
        """
    ).fetchall()
    conn.close()

    shown = [row for row in rows if RANK_ORDER[row["notification_rank"]] >= min_rank_value][: args.top_n]

    print(f"### {args.min_rank}ランク以上の開示（上位{args.top_n}件、スコア降順）\n")
    if not shown:
        print(f"（{args.min_rank}ランク以上の開示はありません）\n")
        return

    print("| Ticker | 会社名 | タイトル | Rank | 材料 | 需給 | テーマ | 合計 |")
    print("|---|---|---|---|---|---|---|---|")
    for row in shown:
        title = row["title"].replace("|", "\\|")
        print(
            f"| {row['ticker']} | {row['company_name']} | {title} | {row['notification_rank']} | "
            f"{row['material_score']} | {row['supply_demand_score']} | {row['theme_score']} | {row['total_score']} |"
        )
    print()


if __name__ == "__main__":
    main()
