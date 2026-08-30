#!/usr/bin/env python3
"""Phase 6: record next-day outcomes for scores that don't have one yet
(spec §10.1). Run this well after scoring, once the relevant next trading
day's price data has actually been collected (see
scripts/collect_case_study_data.py / a future scheduled collector).

Safe to re-run: scores that already have an outcome, or whose next
trading day isn't available yet, are skipped without error.

Usage:
    python scripts/record_outcomes.py --db-path data/stock_radar.db3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_radar.backtest.recorder import record_outcome_for_score  # noqa: E402
from stock_radar.db.connection import get_connection  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-path", default="data/stock_radar.db3")
    args = parser.parse_args()

    conn = get_connection(args.db_path)
    score_ids = [row["score_id"] for row in conn.execute("SELECT score_id FROM scores")]

    recorded = 0
    skip_counts: dict[str, int] = {}
    for score_id in score_ids:
        result = record_outcome_for_score(conn, score_id)
        if result.outcome_id is not None:
            recorded += 1
        else:
            skip_counts[result.skipped_reason] = skip_counts.get(result.skipped_reason, 0) + 1
    conn.commit()
    conn.close()

    print(f"Recorded {recorded} outcome(s) out of {len(score_ids)} score(s).")
    for reason, count in skip_counts.items():
        print(f"  skipped ({reason}): {count}")


if __name__ == "__main__":
    main()
