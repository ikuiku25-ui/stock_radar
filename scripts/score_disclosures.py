#!/usr/bin/env python3
"""Phase 4: score every disclosure in the DB (material/supply-demand/theme,
spec §6.2) under a baseline weight_set and write S/A/B/none ranks.

Safe to re-run: clears prior scores for the weight_set before re-inserting
(see scoring/repository.py's module docstring for why this is done at the
application level rather than a DB constraint).

Usage:
    python scripts/score_disclosures.py --db-path data/stock_radar.db3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_radar.db.connection import get_connection  # noqa: E402
from stock_radar.scoring.repository import delete_scores_for_weight_set, save_score  # noqa: E402
from stock_radar.scoring.scorer import score_disclosure  # noqa: E402
from stock_radar.scoring.weight_sets import ensure_baseline_weight_set  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-path", default="data/stock_radar.db3")
    args = parser.parse_args()

    conn = get_connection(args.db_path)
    weight_set_id = ensure_baseline_weight_set(conn)
    conn.commit()

    delete_scores_for_weight_set(conn, weight_set_id)

    disclosure_ids = [row["disclosure_id"] for row in conn.execute("SELECT disclosure_id FROM disclosures")]

    rank_counts: dict[str, int] = {}
    for disclosure_id in disclosure_ids:
        result = score_disclosure(conn, disclosure_id, weight_set_id)
        save_score(conn, result)
        rank_counts[result.notification_rank] = rank_counts.get(result.notification_rank, 0) + 1
    conn.commit()
    conn.close()

    print(f"Scored {len(disclosure_ids)} disclosure(s) under weight_set_id={weight_set_id}:")
    for rank in ("S", "A", "B", "none"):
        print(f"  {rank}: {rank_counts.get(rank, 0)}")


if __name__ == "__main__":
    main()
